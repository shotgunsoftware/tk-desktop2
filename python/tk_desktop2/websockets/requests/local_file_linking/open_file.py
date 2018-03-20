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
import threading
from sgtk.util.process import subprocess_check_output, SubprocessCalledProcessError
from ..base import WebsocketsRequest


logger = sgtk.LogManager.get_logger(__name__)


class OpenFileWebsocketsRequest(WebsocketsRequest):
    """
    Env var: SHOTGUN_PLUGIN_LAUNCHER
        Get Launcher file name from environement.
        This provides an alternative way to launch applications and open files, instead of os-standard open.

    The request is on the following form:

    {'filepath': '/path/to/file.mov',
     'user': {'entity': {'id': 42,
                      'name': 'John Smith',
                      'status': 'act',
                      'type': 'HumanUser',
                      'valid': 'valid'},
           'group_ids': [3],
           'rule_set_display_name': 'Admin',
           'rule_set_id': 5}},

    Response:
        The generated response is a single boolean, indicating if the open succeeded, false if not.
    """
    def __init__(self, connection, id, parameters):
        super(OpenFileWebsocketsRequest, self).__init__(connection, id)

        if sys.platform.startswith("linux"):
            self._launcher = "xdg-open"
        elif sys.platform == "darwin":
            self._launcher = "open"
        elif sys.platform == "win32":
            self._launcher = None

        if os.environ.get("SHOTGUN_PLUGIN_LAUNCHER"):
            self._launcher = os.environ.get("SHOTGUN_PLUGIN_LAUNCHER")
            logger.debug("Using custom SHOTGUN_PLUGIN_LAUNCHER '%s'" % self._launcher)

        if "filepath" not in parameters:
            raise ValueError("%s: Missing 'filepath' parameter" % self)

        self._path = parameters["filepath"]


    def _execute(self):
        """
        Execute payload
        """
        # TODO: handle error reporting
        if self._launcher is None:
            os.startfile(self._path)
        else:
            try:
                output = subprocess_check_output([self._launcher, self._path])
            except SubprocessCalledProcessError as e:
                # caching failed!
                # TODO: report error message?
                raise RuntimeError(
                    "Could not open file.\nReturn code: %s\nOutput: %s" % (
                        e.returncode,
                        e.output
                    )
                )
        # always return success here (errors handles as exceptions
        success = True
        self._reply(success)


    def execute(self):
        """
        Opens a file with default os association or launcher found in environments. Not blocking.

        :param filepath: String file path (ex: "c:/file.mov")
        :returns: Bool If the operation was successful
        """
        if not os.path.exists(self._path):
            raise RuntimeError("Error opening path [%s]. Path not found." % self._path)

        worker = threading.Thread(target=self._execute)
        worker.daemon = True
        worker.start()





