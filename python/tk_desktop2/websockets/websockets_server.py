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
from . import util

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
        self._sites = {}
        self._request_runner = request_runner
        self._bundle = sgtk.platform.current_bundle()

        # We don't allow requests from sites that SG Create isn't logged into. When we
        # receive a request from another site, we raise a warning dialog telling the user
        # what's going on, but we only do so once per session. This allows us to track
        # whether we've shown the user the warning already and skip it if we have.
        self._has_been_warned_cross_site = False

        # We only want to show the user a warning dialog once if they're logged
        # into Shotgun as a different user than they're logged into Shotgun
        # Create as.
        self._has_been_warned_cross_user = False

        # We're in the situation where we only have access to the HumanUser id from
        # Shotgun, and we only have access to the username from core. We're going to
        # query the username from Shotgun from the given id, so we can cache that in
        # memory.
        self._user_id_to_login_map = dict()

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
            logger.error("Cannot launch websockets: Shotgunlocalhost certificates not enabled.")
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
            logger.error("Websockets certificates failed to load.")
            return

        # Add our callback to process messages.
        self._ws_server.textMessageReceived.connect(self._process_message)
        self._ws_server.newConnectionAdded.connect(self._new_connection)
        self._ws_server.connectionClosed.connect(self._connection_closed)
        self._ws_server.sslErrors.connect(self._on_ssl_errors)

        # Determine which port to run on
        logger.debug("Retreiving websockets port preference from Shotgun.")

        # populate default value
        websockets_port = constants.WEBSOCKETS_PORT_NUMBER

        # get pref from Shotgun
        prefs = self._bundle.shotgun.preferences_read(
            [constants.SHOTGUN_WSS_PORT_PREFERENCE_NAME]
        )

        if constants.SHOTGUN_WSS_PORT_PREFERENCE_NAME in prefs:
            port_value = prefs[constants.SHOTGUN_WSS_PORT_PREFERENCE_NAME]
            logger.debug("Retrieved port value '%s' from Shotgun")
            try:
                websockets_port = int(port_value)
                if websockets_port < 0:
                    raise ValueError()
                elif websockets_port > 65535:
                    raise ValueError()
            except ValueError:
                logger.error("Invalid server port preference set in Shotgun!")
                # details
                logger.warning(
                    "The websockets port preference in Shotgun has the "
                    "invalid value '%s'. It needs to be a positive integer number "
                    "between 0 65535."
                )
        else:
            logger.debug("Port Preference does not exist in Shotgun. Will use default.")

        # Tell the server to listen to the given port
        logger.debug("Starting websockets server on port %s" % constants.WEBSOCKETS_PORT_NUMBER)
        logger.debug("Supports websockets protocol version %s" % constants.WEBSOCKETS_PROTOCOL_VERSION)
        success = self._ws_server.listen(
            QtNetwork.QHostAddress.LocalHost,
            constants.WEBSOCKETS_PORT_NUMBER
        )

        if not success:
            error = self._ws_server.errorString()

            if error == "The bound address is already in use":
                # pop a toast
                logger.error("Cannot start websockets server: Port %s already in use!" % constants.WEBSOCKETS_PORT_NUMBER)
                # add more details to log file
                logger.warning(
                    "Details: The server could not be started because it appears that something is "
                    "already making use of port %d. The most likely cause of this would be "
                    "having more than one instance of Shotgun Create open at the same time, "
                    "or running Shotgun Create and Shotgun "
                    "Desktop simultaneously." % constants.WEBSOCKETS_PORT_NUMBER
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

    def validate_user(self, user_id, shotgun_site):
        """
        Checks to see if the given user id matches what's currently authenticated
        for this site. The first time that this method is called and the user is
        determined to not be valid, the user will be shown a warning dialog with
        information about why they're not receiving a successful request to their
        response. Further attempts to make requests that are not coming from a valid
        user will be logged, but no dialog will be raised.

        :param int user_id: The HumanUser entity id to validate.
        :param shotgun_site: Associated :class:`ShotgunSiteHandler`

        :rtype: bool
        """
        if not shotgun_site.is_authenticated:
            logger.debug(
                "Unable to check the authenticated user because this site is not authenticated."
            )
            return False

        # We have to go from the HumanUser entity id to a login. This is because
        # we don't get the login from Shotgun as part of the payload for a request,
        # and we don't have easy access to the currently-authenticated user's id
        # via tk-core. We'll cache it, though, so we only have to do this once per
        # session.
        if user_id not in self._user_id_to_login_map:
            user_entity = self._bundle.shotgun.find_one(
                "HumanUser",
                [["id", "is", user_id]],
                fields=["login"],
            )

            if not user_entity:
                logger.debug("The user id given (%s) does not exist in Shotgun." % (user_id, ))
                return False

            self._user_id_to_login_map[user_id] = user_entity["login"]

        user_name = self._user_id_to_login_map[user_id]
        current_user = shotgun_site.current_user.login

        logger.debug("Shotgun site user: %s", user_name)
        logger.debug("Shotgun Create user: %s", current_user)

        # We're forcing lowercase here because we ran into an issue on Windows 7
        # where it's possible that a user can login with different casing and it
        # will be maintained. That would cause a problem here if we ended up
        # trying to compare "Jeff" with "jeff", even though they're technically
        # the same user as far as we care here.
        if current_user.lower() != user_name.lower():
            warning_msg = (
                "A request was received from Shotgun from user %s. Shotgun "
                "Create is currently authenticated with user %s, so the "
                "request was rejected. You will need to log into Shotgun "
                "Create as user %s in order to receive Toolkit menu actions "
                "or use local file linking for that user in Shotgun." % (
                    user_name,
                    current_user,
                    user_name
                )
            )
            logger.warning(warning_msg)

            if self._has_been_warned_cross_user:
                logger.debug(
                    "The user has already been warned about being logged into "
                    "Shotgun with a different user than Shotgun Create is "
                    "authenticated with. A warning dialog will not be raised."
                )
            else:
                # Make sure the user is only warned about this once for this
                # connection.
                self._has_been_warned_cross_user = True

                from sgtk.platform.qt import QtGui, QtCore
                msg_box = QtGui.QMessageBox(
                    QtGui.QMessageBox.Warning,
                    "Requesting User Not Authenticated",
                    warning_msg,
                )
                msg_box.setWindowFlags(msg_box.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
                msg_box.exec_()

            return False
        return True

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

            warning_msg = (
                "A request was received from %s. Shotgun Create is currently not logged into "
                "that site, so the request has been rejected. You will need to log into %s from "
                "Shotgun Create in order to see Toolkit menu actions or make use of local file "
                "linking on that Shotgun site." % (origin, origin)
            )
            logger.warning(warning_msg)

            if self._has_been_warned_cross_site:
                logger.debug(
                    "The user has already been shown the cross-site warning dialog -- not showing."
                )
            else:
                from sgtk.platform.qt import QtGui, QtCore
                msg_box = QtGui.QMessageBox(
                    QtGui.QMessageBox.Warning,
                    "Not Authenticated",
                    warning_msg,
                )
                msg_box.setWindowFlags(msg_box.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
                msg_box.exec_()
                self._has_been_warned_cross_site = True

            return

        self._connections[socket_id] = WebsocketsConnection(
            socket_id,
            self._sites[origin],
            self,
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

