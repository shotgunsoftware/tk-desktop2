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

from .certificate_handler import ShotgunCertificateHandler
from .shotgun_site import ShotgunSite
from .errors import ShotgunLocalHostCertNotSupportedError

logger = sgtk.LogManager.get_logger(__name__)

from .connection import WebsocketsConnection


class WebsocketsHandler(object):
    """
    Wraps the websockets server
    """

    def __init__(self, engine_instance_name, plugin_id, base_config, task_manager):
        """
        Start up the engine's built in actions integration.

        This will attempt to bind against a ACTION_MODEL_OBJECT_NAME qt object
        which is assumed to be defined by C++ and establish a data exchange
        between this model and the engine.

        A Shotgun-utils external config instance is constructed to handle
        cross-context requests for actions and execution from the action model.

        :param str engine_instance_name: The instance name of the engine for
            which we should be retrieving commands.
        :param str plugin_id: The plugin id associated with the runtime environment.
        :param str base_config: Descriptor URI for the config to use by default when
            no custom pipeline configs have been defined in Shotgun.
        """
        logger.debug("Begin initializing wss integrations")
        logger.debug("Engine instance name: %s" % engine_instance_name)
        logger.debug("Plugin id: %s" % plugin_id)
        logger.debug("Base config: %s" % base_config)
        self._connections = {}
        self._sites = {}

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
            self._sites[origin] = ShotgunSite(origin)

        self._connections[socket_id] = WebsocketsConnection(
            self._wss_server,
            socket_id,
            self._sites[origin],
            request
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

    def _connection_closed(self, socket_id):
        logger.info("Connection %s was closed." % socket_id)
        # remove from our cache
        if socket_id in self._connections:
            del self._connections[socket_id]

    def _on_ssl_errors(self, errors):
        logger.error("SSL Error: %s" % errors)










