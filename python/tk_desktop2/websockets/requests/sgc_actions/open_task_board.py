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


class OpenTaskBoardInSGCreateWebsocketsRequest(WebsocketsRequest):
    """
    Requests that the task board (overview page) is opened in 
    Shotgun create.

    This is a 'fire-and-forget' command that doesn't return anything.

    Parameters dictionary is expected to be on the following form:

    {'project_id': 123} to indicate that the task board for a given project should be shown
    {'project_id': null} to indicate that the all projects board should be displayed
    """

    def __init__(self, connection, id, parameters):
        """
        :param connection: Associated :class:`WebsocketsConnection`.
        :param int id: Id for this request.
        :param dict params: Parameters payload from websockets.
        """
        super(OpenTaskBoardInSGCreateWebsocketsRequest, self).__init__(connection, id)
        
        # validate
        if "project_id" not in parameters:
            raise ValueError(
                "%s: Missing required 'project_id' key in parameter payload %s" % (self, parameters)
                )

        self._project_id = parameters["project_id"]
        
    def execute(self):
        """
        Execute the payload of the command
        """
        try:
            toolkit_manager = sgtk.platform.current_bundle().toolkit_manager

            path = ShotgunEntityPath()
            path.set_project(self._project_id)

            # TODO - IMPLEMENT THIS METHOD
            # toolkit_manager.emitOpenTaskBoardRequest(path.as_string())
            
            # PLACEHOLDER EXAMPLE CODE (remove later)
            toolkit_manager.emitToast(
                "Open Task Board '%s'" % path.as_string(),
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
