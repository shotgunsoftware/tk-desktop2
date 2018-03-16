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
import json
import pprint
import datetime


logger = sgtk.LogManager.get_logger(__name__)


def open_local_file(self, data):
    """
    Open a file on localhost.

    :param dict data: Message payload.
    """
    try:
        # Retrieve filepath.
        filepath = data.get("filepath")
        result = self.process_manager.open(filepath)

        # Send back information regarding the success of the operation.
        reply = {}
        reply["result"] = result

        self.host.reply(reply)
    except Exception, e:
        self.host.report_error(e.message)


def pick_file_or_directory(self, data):
    """
    Pick single file or directory.

    :param dict data: Message payload. (no data expected)
    """
    files = self.process_manager.pick_file_or_directory(False)
    self.host.reply(files)


def pick_files_or_directories(self, data):
    """
    Pick multiple files or directories.

    :param dict data: Message payload. (no data expected)
    """
    files = self.process_manager.pick_file_or_directory(True)
    self.host.reply(files)
