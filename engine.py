# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from sgtk.platform import Engine
import sgtk
from tank_vendor.shotgun_authentication import ShotgunAuthenticator


class DesktopEngine2(Engine):
    """
    Shotgun Desktop v2 Engine
    """

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
        print self.commands["Shotgun Python Console..."]["callback"]()

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
        self.__desktopserver.launch_desktop_server(
            self._user.host,
            self._current_login["id"],
            parent=None,
        )

    def _emit_log_message(self, handler, record):
        """
        Called by the engine whenever a new log message is available. All log
        messages from the toolkit logging namespace will be passed to this
        method.
        """

        # call out to handler to format message in a standard way
        msg_str = handler.format(record)

        # display message
        print "Desktop engine: %s" % msg_str

