# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import sgtk

logger = sgtk.LogManager.get_logger(__name__)


def get_supported_commands():
    """
    Returns a dictionary enumerating the list of commands supported
    by the server and the class implementation for each.
    """
    # local imports to avoid cyclic deps (these classes derive from WebsocketsRequest)
    from .local_file_linking import PickFileOrDirectoryWebsocketsRequest
    from .local_file_linking import PickFilesOrDirectoriesWebsocketsRequest
    from .local_file_linking import OpenFileWebsocketsRequest
    from .toolkit_actions import ExecuteActionWebsocketsRequest
    from .toolkit_actions import GetActionsWebsocketsRequest
    from .sgc_actions import OpenTaskInSGCreateWebsocketsRequest
    from .sgc_actions import OpenTaskBoardInSGCreateWebsocketsRequest
    from .sgc_actions import OpenVersionDraftInSGCreateWebsocketsRequest
    from .list_commands import ListSupportedCommandsWebsocketsRequest

    # supported commands
    commands = {
        # listing of commands
        "list_supported_commands": {"class": ListSupportedCommandsWebsocketsRequest},
        # toolkit integration
        "get_actions": {"class": GetActionsWebsocketsRequest},
        "execute_action": {"class": ExecuteActionWebsocketsRequest},
        # local file linking
        "pick_file_or_directory": {"class": PickFileOrDirectoryWebsocketsRequest},
        "pick_files_or_directories": {"class": PickFilesOrDirectoriesWebsocketsRequest},
        "open": {"class": OpenFileWebsocketsRequest},
        # shotgun Create integration
        "sgc_open_task": {"class": OpenTaskInSGCreateWebsocketsRequest},
        "sgc_open_task_board": {"class": OpenTaskBoardInSGCreateWebsocketsRequest},
        "sgc_open_version_draft": {
            "class": OpenVersionDraftInSGCreateWebsocketsRequest
        },
    }

    return commands
