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


class OpenVersionInSGCreateWebsocketsRequest(WebsocketsRequest):
    """
    Requests that a version is opened in Shotgun create.

    This is a 'fire-and-forget' command that doesn't return anything.

    Parameters dictionary is expected to be on the following form:

    {
        'version_id': 123
    }     

    Note: Versions with no entity associated are not valid.
    """

    def __init__(self, connection, id, parameters):
        """
        :param connection: Associated :class:`WebsocketsConnection`.
        :param int id: Id for this request.
        :param dict params: Parameters payload from websockets.
        """
        super(OpenVersionInSGCreateWebsocketsRequest, self).__init__(connection, id)
        
        # validate
        if "version_id" not in parameters:
            raise ValueError(
                "%s: Missing required 'version_id' key "
                "in parameter payload %s" % (self, parameters)
                )

        self._version_id = parameters["version_id"]        

    def execute(self):
        """
        Execute the payload of the command
        """
        try:
            engine = sgtk.platform.current_bundle()

            # resolve link and project
            version_data = engine.shotgun.find_one(
                "Version", 
                [["id", "is", self._version_id]],
                ["project", "entity"]
            )

            if version_data["entity"] is None:
                raise RuntimeError("Versions not linked to entities are not supported.")
            
            path = ShotgunEntityPath()
            path.set_project(version_data["project"]["id"])
            path.set_primary_entity(version_data["entity"]["type"], version_data["entity"]["id"])
            path.set_secondary_entity("Version", self._version_id)

            # TODO - IMPLEMENT THIS METHOD
            # engine.toolkit_manager.emitOpenVersionRequest(path.as_string())
            
            # PLACEHOLDER EXAMPLE CODE (remove later)
            engine.toolkit_manager.emitToast(
                "Open Version '%s'" % path.as_string(),
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
