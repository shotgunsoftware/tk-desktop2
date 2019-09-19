# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import sgtk
from ..request import WebsocketsRequest

logger = sgtk.LogManager.get_logger(__name__)


class SetMediaPathInSGCreateWebsocketsRequest(WebsocketsRequest):
    """
    Requests that set the current media in the Shotgun Create player.

    This is a 'fire-and-forget' command that doesn't return anything.

    Parameters dictionary is expected to be on the following form:

    {
        'path': "/path/to/a/file/to/load"
    }

    - path is required and needs to point to a valid path on disk.
    """

    def __init__(self, connection, id, parameters):
        """
        :param connection: Associated :class:`WebsocketsConnection`.
        :param int id: Id for this request.
        :param dict params: Parameters payload from websockets.
        """
        super(SetMediaPathInSGCreateWebsocketsRequest,
              self).__init__(connection, id)

        self._bundle = sgtk.platform.current_bundle()

        # validate
        if "path" not in parameters:
            raise ValueError(
                "%s: Missing required 'path' key "
                "in parameter payload %s" % (self, parameters)
            )

        self._media_path = parameters["path"]

    @property
    def analytics_command_name(self):
        """
        The command name to pass to analytics.
        """
        return "set_media_path"

    def execute(self):
        """
        Execute the payload of the command
        """
        try:
            # call out to Shotgun Create UI to set the media path
            self._bundle.toolkit_manager.emitSetMediaPath(
                self._media_path
            )
        except Exception as e:
            self._reply_with_status(
                status=1,
                error=str(e)
            )
        else:
            self._reply_with_status(0)
