# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import sys
import sgtk
import json
import datetime

from sgtk.platform.qt import QtCore, QtGui
from sgtk.platform.qt5 import QtNetwork, QtWebSockets

from .shotgun_cert_handler import ShotgunCertificateHandler
from .shotgun_site_handler import ShotgunSiteHandler
from .errors import ShotgunLocalHostCertNotSupportedError

logger = sgtk.LogManager.get_logger(__name__)

from .websockets_connection import WebsocketsConnection


class WebsocketsServer(object):
    """
    Wraps the websockets server and manages active connections
    """

    def __init__(self, request_runner):
        """
        A wrapper around the built-in C++ websockets server.
        """
        logger.debug("Begin initializing websockets server wrapper")
        self._connections = {}
        self._sites = {}
        self._request_runner = request_runner

        # retrieve websockets server from C++
        manager = QtCore.QCoreApplication.instance().findChild(QtCore.QObject, "sgtk-manager")
        self._wss_server = manager.findChild(QtWebSockets.QWebSocketServer, "sgtk-web-socket-server")
        logger.debug("Retrieved websockets server %s" % self._wss_server)

        # set up certificates handler
        try:
            self._sg_certs_handler = ShotgunCertificateHandler()
        except ShotgunLocalHostCertNotSupportedError:
            # todo: handle UX around when this is not on?
            logger.error(
                "Shotgun site does not support shotgunlocalhost certificates. "
                "Websockets integration will be disabled."
            )
            return

        # Add our callback to process messages.
        self._wss_server.textMessageReceived.connect(self._process_message)
        self._wss_server.newConnectionAdded.connect(self._new_connection)
        self._wss_server.connectionClosed.connect(self._connection_closed)
        self._wss_server.sslErrors.connect(self._on_ssl_errors)

        # SG certs:
        logger.debug("Set up shotgunlocalhost certificates:")
        logger.debug("Key file: %s" % self._sg_certs_handler.key_path)
        logger.debug("Cert file: %s" % self._sg_certs_handler.cert_path)
        self._wss_server.setSslPem(
            self._sg_certs_handler.key_path,
            self._sg_certs_handler.cert_path
        )

        # TODO: handle port number - read out of sg prefs
        port_number = 9000

        # Tell the server to listen to the given port
        logger.debug("Starting websockets server on port %d" % port_number)
        self._wss_server.listen(
            QtNetwork.QHostAddress.LocalHost,
            port_number
        )
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

        origin = request.rawHeader("origin")
        # origin is a bytearray, convert to string
        origin = str(origin)
        if origin not in self._sites:
            # note: this may pop up a login dialog
            self._sites[origin] = ShotgunSiteHandler(origin)

        # TODO - do we need this?
        #self._sec_websocket_key_header = request.rawHeader("sec-websocket-key")

        self._connections[socket_id] = WebsocketsConnection(
            self._wss_server,
            socket_id,
            self._sites[origin],
            self._request_runner
        )

    def _process_message(self, socket_id, message):
        """
        Message callback

        @param socket_id:
        @param message:
        @return:
        """
        logger.info("Message received from %s." % socket_id)
        # remove from our cache
        if socket_id in self._connections:
            self._connections[socket_id].process_message(message)
        else:
            raise RuntimeError("Got request from unknown connection %s" % socket_id)

    def _connection_closed(self, socket_id):
        logger.info("Connection %s was closed." % socket_id)
        # remove from our cache
        if socket_id in self._connections:
            del self._connections[socket_id]

    def _on_ssl_errors(self, errors):
        logger.error("SSL Error: %s" % errors)

