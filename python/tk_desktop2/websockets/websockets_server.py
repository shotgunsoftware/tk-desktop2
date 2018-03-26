# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import sgtk

from sgtk.platform.qt import QtCore, QtGui
from sgtk.platform.qt5 import QtNetwork, QtWebSockets

from .shotgun_cert_handler import ShotgunCertificateHandler
from .shotgun_site_handler import ShotgunSiteHandler
from .errors import ShotgunLocalHostCertNotSupportedError
from .websockets_connection import WebsocketsConnection

logger = sgtk.LogManager.get_logger(__name__)


class WebsocketsServer(object):
    """
    Wrapper for the build-in websockets server.
    """

    def __init__(self, request_runner):
        """
        :parm request_runner: An associated :class:`RequestRunner`
            instance to handle execution.
        """
        logger.debug("Begin initializing websockets server wrapper")
        self._connections = {}
        self._sites = {}
        self._request_runner = request_runner
        self._bundle = sgtk.platform.current_bundle()

        # retrieve websockets server from C++
        # TODO: this may be done via standard method in the future.
        manager = QtCore.QCoreApplication.instance().findChild(QtCore.QObject, "sgtk-manager")
        self._wss_server = manager.findChild(QtWebSockets.QWebSocketServer, "sgtk-web-socket-server")
        logger.debug("Retrieved websockets server %s" % self._wss_server)

        # set up certificates handler
        try:
            self._sg_certs_handler = ShotgunCertificateHandler()
        except ShotgunLocalHostCertNotSupportedError:
            logger.warning(
                "%s does not support shotgunlocalhost certificates. "
                "Websockets integration will be disabled." % self._bundle.sgtk.shotgun_url
            )
            return

        # SG certs:
        logger.debug("Set up shotgunlocalhost certificates:")
        logger.debug("Key file: %s" % self._sg_certs_handler.key_path)
        logger.debug("Cert file: %s" % self._sg_certs_handler.cert_path)
        self._wss_server.setSslPem(
            self._sg_certs_handler.key_path,
            self._sg_certs_handler.cert_path
        )

        # Add our callback to process messages.
        self._wss_server.textMessageReceived.connect(self._process_message)
        self._wss_server.newConnectionAdded.connect(self._new_connection)
        self._wss_server.connectionClosed.connect(self._connection_closed)
        self._wss_server.sslErrors.connect(self._on_ssl_errors)

        # TODO: handle port number - read out of sg prefs
        port_number = 9000

        # Tell the server to listen to the given port
        logger.debug("Starting websockets server on port %s" % port_number)
        self._wss_server.listen(
            QtNetwork.QHostAddress.LocalHost,
            port_number
        )
        # TODO: In the case another wss is already running, this may cause error singnals
        # to be triggered on the C++ side. We should refactor that so that those signals
        # can bubble up here and be handled by python.
        logger.debug("Websockets server is ready and listening.")

    def destroy(self):
        """
        Should be called upon destruction.
        """
        logger.debug("Begin shutting down wss handler.")
        self._wss_server.close()

    def _new_connection(self, socket_id, name, address, port, request):
        """
        param socket_id: Unique id for the connection
        param request: QNetworkRequest
        """
        logger.debug(
            "New wss connection %s from %s %s %s" % (socket_id, name, address, port)
        )

        # get the site request came from
        origin = request.rawHeader("origin")
        # origin is a bytearray, convert to string
        origin = str(origin)
        if origin not in self._sites:
            # note: this may pop up a login dialog
            self._sites[origin] = ShotgunSiteHandler(origin)

        # TODO - do we need this?? need CR feedback.
        #self._sec_websocket_key_header = request.rawHeader("sec-websocket-key")

        self._connections[socket_id] = WebsocketsConnection(
            self._wss_server,
            socket_id,
            self._sites[origin],
            self._request_runner
        )

    def _process_message(self, socket_id, message):
        """
        Callback firing whenever a message comes in.

        :param str socket_id: Id of the client (browser tab) sending the request.
        :param str message: Raw message from client.
        :raises: RuntimeError on failure.
        """
        logger.debug("Message received from %s." % socket_id)

        # remove from our cache
        if socket_id in self._connections:
            self._connections[socket_id].process_message(message)
        else:
            raise RuntimeError("Got request from unknown connection %s" % socket_id)

    def _connection_closed(self, socket_id):
        """
        Callback firing whenever a websockets connection is closed.

        :param str socket_id: Id of the client (browser tab) sending the request.
        """
        logger.info("Connection %s was closed." % socket_id)

        # remove from our cache
        if socket_id in self._connections:
            del self._connections[socket_id]

    def _on_ssl_errors(self, errors):
        """
        Callback firing whenever ssl errors are detected.

        :param errors: Error details
        """
        logger.error("SSL Error: %s" % errors)

