# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import json
import functools

from sgtk.platform import Engine
import sgtk
from tank_vendor.shotgun_authentication import ShotgunAuthenticator

logger = sgtk.LogManager.get_logger(__name__)

class DesktopEngine2(Engine):
    """
    Shotgun Desktop v2 Engine
    """

    # QObject name for the C++ application engine object
    APPLICATION_ENGINE_OBJECT_NAME = "ApplicationEngine"

    def init_engine(self):
        """
        Main initialization entry point.
        """

    def post_app_init(self):

        # switch to dark styles.
        self._initialize_dark_look_and_feel()

        # test pop up the py console.
        # hack to get this to work due to weird error checks in py console...
        sgtk.platform.engine.g_current_engine = self
        self.commands["Shotgun Python Console..."]["callback"]()

        # We need to initialize current login
        # We know for sure there is a default user, since either the migration was done
        # or we logged in as an actual user with the new installer.
        human_user = ShotgunAuthenticator(
            # We don't want to get the script user, but the human user, so tell the
            # CoreDefaultsManager manager that we are not interested in the script user. Do not use
            # the regular shotgun_authentication.DefaultsManager to get this user because it will
            # not know about proxy information.
            sgtk.util.CoreDefaultsManager(mask_script_user=True)
        ).get_default_user()
        # Cache the user so we can refresh the credentials before launching a background process
        self._user = human_user
        # Retrieve the current logged in user information. This will be used when creating
        # event log entries.
        self._current_login = self.sgtk.shotgun.find_one(
            "HumanUser",
            [["login", "is", human_user.login]],
            ["id", "login"]
        )

        # import and keep a handle on the bundled python module
        self.__tk_desktop2 = self.import_module("tk_desktop2")
        self.__desktopserver = self.__tk_desktop2.desktopserver
        # self.__desktopserver.launch_desktop_server(
        #     self._user.host,
        #     self._current_login["id"],
        #     parent=None,
        # )

        from PySide2 import QtCore, QtNetwork, QtWebSockets
        self._server = QtWebSockets.QWebSocketServer(
            "toolkit",
            QtWebSockets.QWebSocketServer.NonSecureMode,
        )
        self._server.listen(QtNetwork.QHostAddress("ws://localhost"), 9000)
        self._server.newConnection.connect(self._on_new_connection)

    def _on_new_connection(self):
        """

        """
        ws = self._server.nextPendingConnection()
        self.logger.debug("New connection received: %r", ws)
        ws.disconnected.connect(functools.partial(self._on_disconnect, ws))
        ws.textMessageReceived.connect(functools.partial(self._on_message_received, ws))

    def _on_disconnect(self, ws):
        """

        """
        self.logger.debug("Websocket connection closed: %r", ws)

    def _on_message_received(self, ws, message):
        """

        """
        self.logger.debug("Message received: %s", message)
        if message == "get_protocol_version":
            self.logger.debug("Replying with protocol version 2.")
            ws.sendTextMessage(json.dumps(dict(protocol_version=2)))

    def _get_dialog_parent(self):
        """
        Return the QWidget parent for all dialogs created through
        show_dialog and show_modal.
        """
        # parenting logic is inside _create_dialog()
        return None

    def _create_dialog(self, title, bundle, widget, parent):
        """
        Create dialog and parent it to main window
        """

        from sgtk.platform.qt import QtCore, QtGui

        dialog = super(DesktopEngine2, self)._create_dialog(title, bundle, widget, parent)

        logger.debug("Created dialog %s" % dialog)

        application_engine = None
        app = QtCore.QCoreApplication.instance()
        for w in app.children():
            if w.objectName() == self.APPLICATION_ENGINE_OBJECT_NAME:
                application_engine = w
                break

        logger.debug("Found application engine %s" % application_engine)

        if application_engine:
            qml_main_window = application_engine.rootObjects()[0]
            dialog.winId()
            logger.debug("Parenting dialog %s to main window %s" % (dialog, qml_main_window))
            dialog.windowHandle().setTransientParent(qml_main_window)

        return dialog


