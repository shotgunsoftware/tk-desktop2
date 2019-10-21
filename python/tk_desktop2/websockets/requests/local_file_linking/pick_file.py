# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import os
import sgtk
from .sgtk_file_dialog import SgtkFileDialog
from ..request import WebsocketsRequest

logger = sgtk.LogManager.get_logger(__name__)


class PickFileOrFilesWebsocketsRequest(WebsocketsRequest):
    """
    Pops up a modal file selector dialog and lets the user choose
    one or more files or directories.
    Part of the local file linking feature set.
    """

    def __init__(self, connection, id, pick_multiple=False):
        """
        :param connection: Associated :class:`WebsocketsConnection`.
        :param int id: Id for this request.
        :param bool pick_multiple: Flag to indicate whether multi select should be enabled.
        """
        self._pick_multiple = pick_multiple
        super(PickFileOrFilesWebsocketsRequest, self).__init__(connection, id)

    def execute(self):
        """
        Executes modally and synchronously
        """
        dialog = SgtkFileDialog(self._pick_multiple, None)
        dialog.setResolveSymlinks(False)

        # Show modal dialog and get result back.
        result = dialog.exec_()

        files = []
        if result:
            selected_files = dialog.selectedFiles()

            for f in selected_files:
                if os.path.isdir(f):
                    f += os.path.sep
                # Note: Qt returns files with / while the javascript code
                #       expects paths on Windows to use \
                f = f.replace("/", os.path.sep)
                files.append(f)

        self._reply(files)


class PickFilesOrDirectoriesWebsocketsRequest(PickFileOrFilesWebsocketsRequest):
    """
    Command to pick multiple files or directories.

    Pops up a modal file selector dialog and lets the user choose
    one or more files or directories.
    Part of the local file linking feature set.

    Request syntax::

        No parameters are defined for this command

    Expected response::

        A list of file paths as strings.
    """

    def __init__(self, connection, id, parameters):
        """
        :param connection: Associated :class:`WebsocketsConnection`.
        :param int id: Id for this request.
        :param dict parameters: Command parameters (see syntax above)
        :raises: ValueError
        """
        super(PickFilesOrDirectoriesWebsocketsRequest, self).__init__(
            connection, id, pick_multiple=True
        )

    @property
    def analytics_command_name(self):
        """
        The command name to pass to analytics.
        """
        return "local_file_linking_pick_multiple_files"


class PickFileOrDirectoryWebsocketsRequest(PickFileOrFilesWebsocketsRequest):
    """
    Command to pick a single file or directory.

    Pops up a modal file selector dialog
    and lets the user choose one file or directory.
    Part of the local file linking feature set.

    Request syntax::

        No parameters are defined for this command

    Expected response::

        A list of file paths as strings.
    """

    def __init__(self, connection, id, parameters):
        """
        :param connection: Associated :class:`WebsocketsConnection`.
        :param int id: Id for this request.
        :param dict parameters: Command parameters (see syntax above)
        :raises: ValueError
        """
        super(PickFileOrDirectoryWebsocketsRequest, self).__init__(
            connection, id, pick_multiple=False
        )

    @property
    def analytics_command_name(self):
        """
        The command name to pass to analytics.
        """
        return "local_file_linking_pick_single_file"
