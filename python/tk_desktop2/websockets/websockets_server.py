# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import sgtk
import json
import traceback

from sgtk.platform.qt import QtCore, QtGui
from sgtk.platform.qt5 import QtNetwork, QtWebSockets

from .shotgun_cert_handler import ShotgunCertificateHandler
from .errors import ShotgunLocalHostCertNotSupportedError
from .websockets_connection import WebsocketsConnection
from .encryption_handler import EncryptionHandler

from . import constants

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
        self._request_runner = request_runner
        self._bundle = sgtk.platform.current_bundle()

        # retrieve websockets server from C++
        # TODO: this may be done via standard method in the future.
        manager = self._bundle.toolkit_manager
        server_name = manager.initializeWebSocketServer(True)
        self._ws_server = QtCore.QCoreApplication.instance().findChild(
            QtCore.QObject, server_name
        )
        logger.debug("Retrieved websockets server %s" % self._ws_server)

        # set up certificates handler
        try:
            self._sg_certs_handler = ShotgunCertificateHandler()
        except ShotgunLocalHostCertNotSupportedError:
            logger.error(
                "Cannot launch websockets: Shotgunlocalhost certificates not enabled."
            )
            return

        # SG certs:
        logger.debug("Set up shotgunlocalhost certificates:")
        logger.debug("Key file: %s" % self._sg_certs_handler.key_path)
        logger.debug("Cert file: %s" % self._sg_certs_handler.cert_path)
        success = self._ws_server.setSslPem(
            self._sg_certs_handler.key_path, self._sg_certs_handler.cert_path
        )
        if not success:
            logger.error("Websockets certificates failed to load.")
            return

        # set up encryption handler for our current site
        self._encryption_handler = EncryptionHandler()

        # Add our callback to process messages.
        self._ws_server.textMessageReceived.connect(self._process_message_wrapper)
        self._ws_server.newConnectionAdded.connect(self._new_connection_wrapper)
        self._ws_server.connectionClosed.connect(self._connection_closed)
        self._ws_server.sslErrors.connect(self._on_ssl_errors)

        # Determine which port to run on
        logger.debug("Retreiving websockets port preference from Shotgun.")

        # populate default value
        websockets_port = constants.WEBSOCKETS_PORT_NUMBER

        # get pref from Shotgun
        prefs = self._bundle.shotgun.preferences_read(
            [constants.SHOTGUN_CREATE_PREFS_NAME]
        )

        logger.debug(
            "Looking for preference '%s' and key '%s'..."
            % (
                constants.SHOTGUN_CREATE_PREFS_NAME,
                constants.SHOTGUN_CREATE_PREFS_WEBSOCKETS_PORT_KEY,
            )
        )
        if constants.SHOTGUN_CREATE_PREFS_NAME in prefs:
            prefs_dict = json.loads(prefs[constants.SHOTGUN_CREATE_PREFS_NAME])
            if constants.SHOTGUN_CREATE_PREFS_WEBSOCKETS_PORT_KEY in prefs_dict:
                websockets_port = prefs_dict[
                    constants.SHOTGUN_CREATE_PREFS_WEBSOCKETS_PORT_KEY
                ]
                logger.debug(
                    "...retrieved port value '%s' from Shotgun prefs" % websockets_port
                )

        # Tell the server to listen to the given port
        logger.debug("Starting websockets server on port %s" % websockets_port)
        logger.debug(
            "Supports websockets protocol version %s"
            % constants.WEBSOCKETS_PROTOCOL_VERSION
        )
        success = self._ws_server.listen(
            QtNetwork.QHostAddress.LocalHost, websockets_port
        )

        if not success:
            error = self._ws_server.errorString()

            if error == "The bound address is already in use":
                # the error will generate a toast in the create UI
                logger.error(
                    "Cannot start websockets server: Port %s already in use!"
                    % websockets_port
                )
                # add more details to log file
                logger.warning(
                    "Details: The server could not be started because it appears that something is "
                    "already making use of port %d. The most likely cause of this would be "
                    "having more than one instance of Shotgun Create open at the same time, "
                    "or running Shotgun Create and Shotgun "
                    "Desktop simultaneously." % websockets_port
                )
            else:
                logger.error("Cannot start websockets server: %s" % error)
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

    @property
    def websockets_server(self):
        """
        The encapsulated :class:`QWebsocketsServer` object.
        """
        return self._ws_server

    @property
    def request_runner(self):
        """
        The associated :class:`RequestRunner` object.
        """
        return self._request_runner

    def _new_connection_wrapper(self, socket_id, name, address, port, request):
        """
        Callback wrapper that fires when a new websockets connection is requested.
        For details, see _new_connecton.
        """
        # add a try-except clause, otherwise exceptions are consumed by QT
        # note - not using a lambda around the signal due to garbage
        # connection issues - this produces memory leaks.
        try:
            self._new_connection(socket_id, name, address, port, request)
        except Exception:
            logger.warning(
                "Exception raised in QT new connection signal.\n "
                "Message and details: \n\n %s" % (traceback.format_exc())
            )

    def _process_message_wrapper(self, socket_id, message):
        """
        Callback wrapper that fires when a new message arrives.
        For details, see _process_message.
        """
        # add a try-except clause, otherwise exceptions are consumed by QT
        # note - not using a lambda around the signal due to garbage
        # connection issues - this produces memory leaks.
        try:
            self._process_message(socket_id, message)
        except Exception:
            logger.warning(
                "Exception raised in QT process message signal.\n "
                "Message and details: \n\n %s" % (traceback.format_exc())
            )

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

        # The origin coming from the request's raw header will be a bytearray. We're
        # going to want it as a string, so we'll go ahead and convert it right away.
        origin_site = str(request.rawHeader("origin"))

        self._connections[socket_id] = WebsocketsConnection(
            socket_id, origin_site, self._encryption_handler, self
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
