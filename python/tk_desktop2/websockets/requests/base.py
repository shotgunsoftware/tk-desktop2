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
    def create(cls, connection, request_id, command):
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
                connection,
                request_id,
                command_data
            )

        elif command_name == "execute_action":
            return ExecuteActionWebsocketsRequest(
                connection,
                request_id,
                command_data
            )

        elif command_name == "pick_file_or_directory":
            return PickFileOrDirectoryWebsocketsRequest(
                connection,
                request_id,
                command_data,
                pick_multiple=False
            )

        elif command_name == "pick_files_or_directories":
            return PickFileOrDirectoryWebsocketsRequest(
                connection,
                request_id,
                command_data,
                pick_multiple=True
            )

        elif command_name == "open":
            return OpenFileWebsocketsRequest(
                connection,
                request_id,
                command_data
            )

        else:
            raise RuntimeError("Unsupported command '%s'" % command_name)

    def __init__(self, connection, id):
        self._connection = connection
        self._id = id

    def __repr__(self):
        return "<%s id %s@%s>" % (self.__class__.__name__, self._id, self._connection)

    @property
    def project_id(self):
        """
        Project id associated with this request or None for a site wide request
        """
        return None

    @property
    def entity_type(self):
        """
        Entity type associated with this request or None for a site wide request
        """
        return None

    @property
    def entity_id(self):
        """
        Entity id associated with this request or None for a site wide request
        """
        return None

    @property
    def linked_entity_type(self):
        """
        Linked entity type associated with this request or None if not applicable.
        Linked entity types are useful to distinguish for example a configuration
        difference between tasks linked to shots vs tasks linked to assets.
        """
        return None

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

    def _reply(self, data):
        """
        Sends back a reply to the client
        """
        self._connection.reply(data, self._id)
