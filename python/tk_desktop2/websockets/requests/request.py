# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#
import sgtk

logger = sgtk.LogManager.get_logger(__name__)


class WebsocketsRequest(object):
    """
    Base class that represents a web sockets request.

    Requests are created via the `WebsocketsRequest.create` factory classmethod
    and each different command supported by the engine is represented by a class.

    The following requests are currently supported:

    - get_actions - list Toolkit actions.
    - execute_action - execute Toolkit action.
    - pick_file_or_directory - select single item.
    - pick_files_or_directories - select multiple items.
    - open - open a file on disk.
    """

    @classmethod
    def create(cls, connection, request_id, command):
        """
        Request factory. Creates and returns a suitable :class:`WebsocketsRequest`
        instance given the input parameters.

        :param connection: Associated :class:`WebsocketsConnection`.
        :param int request_id: Id for this request.
        :param dict command: Command payload.
        :returns: Object deriving from :class:`WebsocketsRequest`.
        :raises: RuntimeError on protocol errors.
        """
        # local imports to avoid cyclic deps (these classes derive from WebsocketsRequest)
        from .local_file_linking import PickFileOrDirectoryWebsocketsRequest
        from .local_file_linking import OpenFileWebsocketsRequest
        from .toolkit_actions import ExecuteActionWebsocketsRequest
        from .toolkit_actions import GetActionsWebsocketsRequest
        from .sgc_actions import OpenTaskInSGCreateWebsocketsRequest
        from .sgc_actions import OpenTaskBoardInSGCreateWebsocketsRequest
        from .sgc_actions import OpenVersionInSGCreateWebsocketsRequest
        
        

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
        elif command_name == "sgc_open_task":
            return OpenTaskInSGCreateWebsocketsRequest(
                connection,
                request_id,
                command_data
            )
        elif command_name == "sgc_open_task_board":
            return OpenTaskBoardInSGCreateWebsocketsRequest(
                connection,
                request_id,
                command_data
            )
        elif command_name == "sgc_open_version":
            return OpenVersionInSGCreateWebsocketsRequest(
                connection,
                request_id,
                command_data
            )
        elif command_name == "pick_file_or_directory":
            return PickFileOrDirectoryWebsocketsRequest(
                connection,
                request_id,
                pick_multiple=False
            )
        elif command_name == "pick_files_or_directories":
            return PickFileOrDirectoryWebsocketsRequest(
                connection,
                request_id,
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
        """
        :param connection: Associated :class:`WebsocketsConnection`.
        :param int id: Id for this request.
        """
        self._connection = connection
        self._id = id

    def __repr__(self):
        """
        String representation
        """
        return "<%s id %s@%s>" % (
            self.__class__.__name__,
            self._id,
            self._connection
        )

    @property
    def requires_toolkit(self):
        """
        True if the request requires toolkit for its execution, false if not.
        """
        return False

    @property
    def project_id(self):
        """
        Project id associated with this request or None for a generic request
        """
        return None

    @property
    def entity_type(self):
        """
        Entity type associated with this request or None for a generic request
        """
        return None

    @property
    def entity_id(self):
        """
        Entity id associated with this request or None for a generic request
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

    def execute(self):
        """
        Executes non-toolkit style request.
        Implemented by deriving classes.
        """
        raise NotImplementedError(
            "WebsocketsRequest.execute not implemented by deriving class."
        )

    def execute_with_context(self, associated_commands):
        """
        Executes toolkit style request. Passes a fully loaded external
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

        :param list associated_commands: See above for details.
        """
        raise NotImplementedError(
            "WebsocketsRequest.execute_with_context not implemented by deriving class."
        )

    def _reply(self, data):
        """
        Sends back a reply to the client.

        :param object data: Data to send to client.
        """
        self._connection.reply(data, self._id)

    def _reply_with_status(self, status=0, output=None, error=None):
        """
        Sends back a standard status report

        :param int status: Status code (0 means success)
        :param str output: Messages
        :param str error: Error messages
        """
        self._reply(
            {
                "retcode": status,
                "out": (output or ""),
                "err": (error or ""),
            }
        )
