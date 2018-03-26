# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import os
import sgtk
from .sgtk_file_dialog import SgtkFileDialog
from ..base import WebsocketsRequest

logger = sgtk.LogManager.get_logger(__name__)


class PickFileOrDirectoryWebsocketsRequest(WebsocketsRequest):
    """

    """
    def __init__(self, connection, id, parameters, pick_multiple):
        self._pick_multiple = pick_multiple
        super(PickFileOrDirectoryWebsocketsRequest, self).__init__(connection, id)

    def execute(self):
        dialog = SgtkFileDialog(self._pick_multiple, None)
        dialog.setResolveSymlinks(False)

        # Get result.
        result = dialog.exec_()

        files = []
        if result:
            selected_files = dialog.selectedFiles()

            for f in selected_files:
                if os.path.isdir(f):
                    f += os.path.sep
                files.append(f)

        # Note: Qt returns files with / while the javascript code expects paths on Windows to use \
        files = [f.replace("/", os.path.sep) for f in files]

        self._reply(files)

