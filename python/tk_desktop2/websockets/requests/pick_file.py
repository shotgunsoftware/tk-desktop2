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
import sgtk
from .sgtk_file_dialog import SgtkFileDialog
from .base import WebsocketsRequest

logger = sgtk.LogManager.get_logger(__name__)


class PickFileOrDirectoryWebsocketsRequest(WebsocketsRequest):

    def __init__(self, connection, id, parameters, pick_multiple):
        self._pick_multiple = pick_multiple
        super(PickFileOrDirectoryWebsocketsRequest, self).__init__(connection, id)

    # def execute(self):
    #     dialog = SgtkFileDialog(self._pick_multiple, None)
    #     dialog.setResolveSymlinks(False)
    #
    #     # Get result.
    #     result = dialog.exec_()
    #
    #     files = []
    #     if result:
    #         selected_files = dialog.selectedFiles()
    #
    #         for f in selected_files:
    #             if os.path.isdir(f):
    #                 f += os.path.sep
    #             files.append(f)
    #
    #     # Note: Qt returns files with / while the javascript code expects paths on Windows to use \
    #     files = [f.replace("/", os.pathsep) for f in files]
    #
    #     self.connection.reply(files, self.id)
    #

    def execute(self, configurations):
        """
        Executes the request. Passes a fully loaded external
        configuration state to aid execution, laid out in the following
        structure:

        [
            {
                "configuration": <ExternalConfiguration>,
                "commands": [<ExternalCommand>, ...],
                "error": None
            },
            {
                "configuration": <ExternalConfiguration>,
                "commands": None,
                "error": "Something went wrong"
            },
        ]

        :param list configurations: See above for details.
        """
        raise NotImplementedError("WebsocketsRequest.execute not implemented by deriving class.")
