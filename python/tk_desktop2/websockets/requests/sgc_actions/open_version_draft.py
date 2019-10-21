# Copyright 2019 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import sgtk
from ..request import WebsocketsRequest
from ....shotgun_entity_path import ShotgunEntityPath

logger = sgtk.LogManager.get_logger(__name__)


class OpenVersionDraftInSGCreateWebsocketsRequest(WebsocketsRequest):
    """
    Requests that sets the current draft in the Shotgun Create player.

    This is a 'fire-and-forget' command that doesn't return anything.

    Parameters dictionary is expected to be of the following form:

    {
        'task_id': 123,
        'path': "/path/to/a/file/to/load/as/draft",
        ['version_data': {"sg_field_1": "sg_field_1_value", "sg_field_2", "sg_field_2_value"}]
    }

    - task_id is required and needs to point to a task associated with an entity.
    - path is required and needs to point to a valid path on disk.
    """

    def __init__(self, connection, id, parameters):
        """
        :param connection: Associated :class:`WebsocketsConnection`.
        :param int id: Id for this request.
        :param dict params: Parameters payload from websockets.
        """
        super(OpenVersionDraftInSGCreateWebsocketsRequest, self).__init__(
            connection, id
        )

        self._bundle = sgtk.platform.current_bundle()

        if "task_id" not in parameters:
            raise ValueError(
                "%s: Missing required 'task_id' key "
                "in parameter payload %s" % (self, parameters)
            )
        self._task_id = parameters["task_id"]

        if "path" not in parameters:
            raise ValueError(
                "%s: Missing required 'path' key "
                "in parameter payload %s" % (self, parameters)
            )
        self._draft_path = parameters["path"]

        self._version_data = parameters.get("version_data", "{}")

    @property
    def analytics_command_name(self):
        """
        The command name to pass to analytics.
        """
        return "open_version_draft"

    def execute(self):
        """
        Execute the payload of the command
        """
        try:
            engine = sgtk.platform.current_engine()

            # open task - resolve link and project
            task_data = engine.shotgun.find_one(
                "Task", [["id", "is", self._task_id]], ["project", "entity"]
            )

            if task_data is None:
                raise ValueError(
                    "Task id %d cannot be found in Shotgun!" % (self._task_id,)
                )

            if task_data["entity"] is None:
                raise RuntimeError("Tasks not linked to entities are not supported.")

            task_path = ShotgunEntityPath()
            task_path.set_project(task_data["project"]["id"])
            task_path.set_primary_entity(
                task_data["entity"]["type"], task_data["entity"]["id"]
            )
            task_path.set_secondary_entity("Task", self._task_id)

            # call out to Shotgun Create UI to set the media path
            self._bundle.toolkit_manager.emitOpenVersionDraft(
                task_path.as_string(), self._draft_path, self._version_data
            )
        except Exception as e:
            self._bundle.logger.exception(e)
            self._reply_with_status(status=1, error=str(e))
        else:
            self._reply_with_status(0)
