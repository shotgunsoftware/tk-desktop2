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


logger = sgtk.LogManager.get_logger(__name__)


class WebsocketsRequest(object):

    @classmethod
    def create(cls, request_id, command):
        """
        Request factory
        """

        from .pick_file import PickFileOrDirectoryWebsocketsRequest
        from .execute_action import ExecuteActionWebsocketsRequest
        from .get_actions import GetActionsWebsocketsRequest
        from .open_file import OpenFileWebsocketsRequest

        # commands are on the following form:
        # {
        #     'data': {
        #         'entity_id': 584,
        #         'entity_type': 'Project',
        #         'project_id': 584,
        #         'user': {...},
        #     },
        #     'name': 'get_actions'
        # }

        command_name = command["name"]
        command_data = command["data"]

        if command_name == "get_actions":
            return GetActionsWebsocketsRequest(
                request_id,
                command_data
            )

        elif command_name == "execute_action":
            return ExecuteActionWebsocketsRequest(
                request_id,
                command_data
            )

        elif command_name == "pick_file_or_directory":
            return PickFileOrDirectoryWebsocketsRequest(
                request_id,
                command_data,
                pick_multiple=False
            )

        elif command_name == "pick_files_or_directories":
            return PickFileOrDirectoryWebsocketsRequest(
                request_id,
                command_data,
                pick_multiple=True
            )

        elif command_name == "open":
            return OpenFileWebsocketsRequest(
                request_id,
                command_data
            )

        else:
            raise RuntimeError("Unsupported command '%s'" % command_name)

    def __init__(self, id, connection):
        self._id = id
        self._connection = connection

    def __repr__(self):
        return "<%s id %s@%s>" % (self.__class__.__name__, self.id, self.connection)

    @property
    def id(self):
        """
        The id for this request
        """
        return self._id

    @property
    def connection(self):
        """
        The associated connection
        """
        return self._connection

