# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import sgtk
from ..request import WebsocketsRequest
from ....shotgun_entity_path import ShotgunEntityPath

logger = sgtk.LogManager.get_logger(__name__)


class OpenTaskInSGCreateWebsocketsRequest(WebsocketsRequest):
    """
    Requests that a task or version is opened in Shotgun create.

    This is a 'fire-and-forget' command that doesn't return anything.

    Parameters dictionary is expected to be on the following form:

    {
        'task_id': 123, ['version_id': 123]
    }

    - task_id is required and needs to point to a task associated with an entity.
    - version_id is optional. If this key is specified, it needs to point at
      a version that is linked to the task specified by the task_id.
    """

    def __init__(self, connection, id, parameters):
        """
        :param connection: Associated :class:`WebsocketsConnection`.
        :param int id: Id for this request.
        :param dict params: Parameters payload from websockets.
        """
        super(OpenTaskInSGCreateWebsocketsRequest, self).__init__(connection, id)

        self._bundle = sgtk.platform.current_bundle()

        # validate
        if "task_id" not in parameters:
            raise ValueError(
                "%s: Missing required 'task_id' key "
                "in parameter payload %s" % (self, parameters)
            )

        self._task_id = parameters["task_id"]
        if "version_id" in parameters:
            self._version_id = parameters["version_id"]
        else:
            self._version_id = None

    @property
    def analytics_command_name(self):
        """
        The command name to pass to analytics.
        """
        return "open_create_task"

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

            version_path_str = None

            # validate that if a version exists, it's correctly linked to the task
            if self._version_id:
                version_data = engine.shotgun.find_one(
                    "Version",
                    [
                        ["id", "is", self._version_id],
                        ["sg_task", "is", {"id": self._task_id, "type": "Task"}],
                    ],
                    ["project", "entity"],
                )

                if version_data is None:
                    raise ValueError(
                        "Version %d with task %d cannot be "
                        "found in Shotgun!" % (self._version_id, self._task_id)
                    )

                version_path = ShotgunEntityPath()
                version_path.set_project(version_data["project"]["id"])
                version_path.set_primary_entity(
                    version_data["entity"]["type"], version_data["entity"]["id"]
                )
                version_path.set_secondary_entity("Version", self._version_id)
                version_path_str = version_path.as_string()

            # call out to Shotgun Create UI to focus on the task
            self._bundle.toolkit_manager.emitOpenTaskRequest(
                task_path.as_string(), version_path_str
            )

        except Exception as e:
            self._bundle.logger.exception(e)
            self._reply_with_status(status=1, error=str(e))
        else:
            self._reply_with_status(0)
