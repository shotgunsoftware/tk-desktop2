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
        :param request_runner: An associated :class:`RequestRunner`
            instance to handle execution.
        """
        logger.debug("Begin initializing websockets server wrapper")
        self._connections = {}
        self._sites = {}
        self._request_runner = request_runner
        self._bundle = sgtk.platform.current_bundle()
        self._has_been_warned_cross_site = False

        # retrieve websockets server from C++
        # TODO: this may be done via standard method in the future.
        manager = self._bundle.toolkit_manager
        server_name = manager.initializeWebSocketServer(True)
        self._ws_server = QtCore.QCoreApplication.instance().findChild(QtCore.QObject, server_name)
        logger.debug("Retrieved websockets server %s" % self._ws_server)

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
        success = self._ws_server.setSslPem(
            self._sg_certs_handler.key_path,
            self._sg_certs_handler.cert_path
        )
        if not success:
            raise RuntimeError("Could not set up Websockets certificates.")

        # Add our callback to process messages.
        self._ws_server.textMessageReceived.connect(self._process_message)
        self._ws_server.newConnectionAdded.connect(self._new_connection)
        self._ws_server.connectionClosed.connect(self._connection_closed)
        self._ws_server.sslErrors.connect(self._on_ssl_errors)

        # TODO: handle port number - read out of sg prefs
        port_number = 9000

        # Tell the server to listen to the given port
        logger.debug("Starting websockets server on port %s" % port_number)
        success = self._ws_server.listen(
            QtNetwork.QHostAddress.LocalHost,
            port_number
        )

        if not success:
            error = self._ws_server.errorString()

            if error == "The bound address is already in use":
                logger.warning(
                    "The server could not be started because it appears that something is "
                    "already making use of port %d. The most likely cause of this would be "
                    "having more than one instance of Shotgun Create open at the same time, "
                    "or running Shotgun Create and Shotgun Desktop simultaneously." % port_number
                )
            else:
                logger.warning("Websockets server could not be started: %s" % error)
        else:
            logger.debug("Websockets server is ready and listening.")

    def destroy(self):
        """
        Should be called upon destruction.
        """
        logger.debug("Begin shutting down internal C++ websockets server.")
        self._ws_server.close()
        # set to none for GC
        self._ws_server = None

    def _new_connection(self, socket_id, name, address, port, request):
        """
        Callback that fires when a new websockets connection is requested.

        :param str socket_id: Unique id for the connection
        :param str name: Name of connection
        :param int port: Port that connection is using.
        :param request: QNetworkRequest object describing the request.
        """
        logger.debug(
            "New ws connection %s from %s %s %s" % (socket_id, name, address, port)
        )

        # get the site where the request came from as a bytearray, and convert to string
        origin = str(request.rawHeader("origin"))

        if origin not in self._sites:
            # This will NEVER pop up a login dialog. If we're not already authenticated
            # with the site, then we do not continue and we close the connection below.
            self._sites[origin] = ShotgunSiteHandler(origin)

        # We do not allow cross-site connections, meaning that if we're not already
        # authenticated with the site requesting a connection, we immediately close
        # it and show the user a one-time warning message.
        if not self._sites[origin].is_authenticated:
            self._ws_server.closeConnection(socket_id)
            logger.warning("Not authenticated with %s -- the connection has been closed.", origin)

            if self._has_been_warned_cross_site:
                logger.debug(
                    "The user has already been shown the cross-site warning dialog -- not showing."
                )
            else:
                from sgtk.platform.qt import QtGui, QtCore
                msg_box = QtGui.QMessageBox(
                    QtGui.QMessageBox.Warning,
                    "Not Authenticated",
                    "Shotgun Create is not authenticated with %s. Please log into "
                    "this site in Shotgun Create if you require Toolkit menu actions "
                    "or local file links." % origin
                )
                msg_box.setWindowFlags(msg_box.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
                msg_box.exec_()
                self._has_been_warned_cross_site = True

            return

        self._connections[socket_id] = WebsocketsConnection(
            self._ws_server,
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
        logger.debug("Connection %s was closed." % socket_id)

        # remove from our cache
        if socket_id in self._connections:
            del self._connections[socket_id]

    def _on_ssl_errors(self, errors):
        """
        Callback firing whenever ssl errors are detected.

        :param errors: Error details
        """
        logger.error("SSL Error: %s" % errors)

