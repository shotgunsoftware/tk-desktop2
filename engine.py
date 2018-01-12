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

