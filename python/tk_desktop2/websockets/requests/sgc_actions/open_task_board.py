# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import sgtk
from ..request import WebsocketsRequest

logger = sgtk.LogManager.get_logger(__name__)


class OpenTaskBoardInSGCreateWebsocketsRequest(WebsocketsRequest):
    """
    Requests that the task board (overview page) is opened in Shotgun Create.

    This is a 'fire-and-forget' command that doesn't return anything.

    Parameters dictionary is expected to be on the following form:

    {'project_id': 123|null, ['task_id': 123|null]}

    Parameter details:

    - project_id: If set to null, indicates that the project board for all
                  projects should be displayed. If set to a project id,
                  the project id for this specific project is displayed.
    - task_id:    An optional task to select. If a project_id is selected,
                  this task should belong to that given project. If set to
                  null, no task is selected.
    """

    def __init__(self, connection, id, parameters):
        """
        :param connection: Associated :class:`WebsocketsConnection`.
        :param int id: Id for this request.
        :param dict params: Parameters payload from websockets.
        """
        super(OpenTaskBoardInSGCreateWebsocketsRequest, self).__init__(connection, id)

        self._bundle = sgtk.platform.current_bundle()

        # validate
        if "project_id" not in parameters:
            raise ValueError(
                "%s: Missing required 'project_id' key in parameter payload %s"
                % (self, parameters)
            )
        else:
            self._project_id = parameters["project_id"]

        if "task_id" not in parameters:
            self._task_id = None
        else:
            self._task_id = parameters["task_id"]

    @property
    def analytics_command_name(self):
        """
        The command name to pass to analytics.
        """
        return "open_create_task_board"

    def execute(self):
        """
        Execute the payload of the command
        """
        try:
            # validate that the project id belongs to a valid project
            if self._project_id:
                project_data = self._bundle.shotgun.find_one(
                    "Project", [["id", "is", self._project_id]]
                )
                if not project_data:
                    raise ValueError("Invalid project id!")

            # validate that the task id belongs to a valid project
            # and if a project is specified, that it is linked to
            # that project
            if self._task_id:
                filters = [["id", "is", self._task_id]]
                if self._project_id:
                    filters.append(
                        ["project", "is", {"id": self._project_id, "type": "Project"}]
                    )

                task_data = self._bundle.shotgun.find_one("Task", filters)
                if not task_data:
                    raise ValueError("Invalid task id!")

            self._bundle.toolkit_manager.emitOpenTaskBoardRequest(
                self._project_id, self._task_id
            )
        except Exception as e:
            self._bundle.logger.exception(e)
            self._reply_with_status(status=1, error=str(e))
        else:
            self._reply_with_status(0)
