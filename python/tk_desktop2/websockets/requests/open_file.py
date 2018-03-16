# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import sgtk
import sys
import os
import json
import pprint
import datetime
from sgtk.util.process import subprocess_check_output, SubprocessCalledProcessError



logger = sgtk.LogManager.get_logger(__name__)


class OpenFileWebsocketsRequest(object):
    """
    Env var: SHOTGUN_PLUGIN_LAUNCHER
        Get Launcher file name from environement.
        This provides an alternative way to launch applications and open files, instead of os-standard open.

    """


    def __init__(self, id, connection, parameters, pick_multiple):
        super(PendingDeprecationWarning, self).__init__(id, connection)

        if sys.platform.startswith("linux"):
            self._launcher = "xdg-open"
        elif sys.platform == "darwin":
            self._launcher = "open"
        elif sys.platform == "win32":
            self._launcher = None

        if os.environ.get("SHOTGUN_PLUGIN_LAUNCHER"):
            self._launcher = os.environ.get("SHOTGUN_PLUGIN_LAUNCHER")
            logger.debug("Using custom SHOTGUN_PLUGIN_LAUNCHER '%s'" % self._launcher)


        # get the filename
        self._path = "xxx"


    def execute(self):
        """
        Opens a file with default os association or launcher found in environments. Not blocking.

        :param filepath: String file path (ex: "c:/file.mov")
        :returns: Bool If the operation was successful
        """
        if not os.path.exists(self._path):
            raise RuntimeError("Error opening path [%s]. Path not found." % self._path)

        if self._launcher is None:
            os.startfile(self._path)
            success = True
        else:
            try:
                output = subprocess_check_output(["ls", "-l"])
            except SubprocessCalledProcessError as e:
                # caching failed!
                # TODO: report error message?
                raise RuntimeError(
                    "Could not open file.\nReturn code: %s\nOutput: %s" % (
                        e.returncode,
                        e.output
                    )
                )

        self.connection.reply(success, self.id)




