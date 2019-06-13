# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import os
import sgtk
from ..request import WebsocketsRequest
from ....shotgun_entity_path import ShotgunEntityPath

logger = sgtk.LogManager.get_logger(__name__)


class OpenTaskInSGCreateWebsocketsRequest(WebsocketsRequest):
    """
    Requests that a task is opened in Shotgun create.

    This is a 'fire-and-forget' command that doesn't return anything.

    Parameters dictionary is expected to be on the following form:

    {
        'project_id': 123, 
        'entity_type': 'Shot', 
        'entity_id': 123,
        'task_id': 123
    }     

    Note: Tasks with no entity associated are not valid.
    """

    def __init__(self, connection, id, parameters):
        """
        :param connection: Associated :class:`WebsocketsConnection`.
        :param int id: Id for this request.
        :param dict params: Parameters payload from websockets.
        """
        super(OpenTaskInSGCreateWebsocketsRequest, self).__init__(connection, id)
        
        # validate
        for field in ["project_id", "entity_type", "entity_id", "task_id"]:
            if field not in parameters:
                raise ValueError(
                    "%s: Missing required '%s' key "
                    "in parameter payload %s" % (self, field, parameters)
                    )

        self._project_id = parameters["project_id"]
        self._entity_type = parameters["entity_type"]
        self._entity_id = parameters["entity_id"]
        self._task_id = parameters["task_id"]

    def execute(self):
        """
        Execute the payload of the command
        """
        try:
            toolkit_manager = sgtk.platform.current_bundle().toolkit_manager

            path = ShotgunEntityPath()
            path.set_project(self._project_id)
            path.set_primary_entity(self._entity_type, self._entity_id)
            path.set_secondary_entity("Task", self._task_id)

            # TODO - IMPLEMENT THIS METHOD
            # toolkit_manager.emitOpenTaskRequest(path.as_string())
            
            # PLACEHOLDER EXAMPLE CODE (remove later)
            toolkit_manager.emitToast(
                "Open Task '%s'" % path.as_string(),
                "info",
                False # Not persistent, meaning it'll stay for 5 seconds and disappear.
            )
        except Exception as e:
            self._reply_with_status(
                status=1,
                error=str(e)
            )
        else:
            self._reply_with_status(0)
