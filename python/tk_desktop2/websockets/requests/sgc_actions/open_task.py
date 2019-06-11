# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import os
import sgtk
from ..request import WebsocketsRequest

logger = sgtk.LogManager.get_logger(__name__)


class OpenTaskInSGCreateWebsocketsRequest(WebsocketsRequest):
    """
    """
    def __init__(self, connection, id, parameters):
        """
        :param connection: Associated :class:`WebsocketsConnection`.
        :param int id: Id for this request.
        :param bool pick_multiple: Flag to indicate whether multi select should be enabled.
        """
        self._params = parameters
        super(OpenTaskInSGCreateWebsocketsRequest, self).__init__(connection, id)

    def execute(self):
        """
        Execute the payload of the command
        """
        try:
            toolkit_manager = sgtk.platform.current_bundle().toolkit_manager
            toolkit_manager.emitToast(
                "Open Task: %s" % str(self._params),
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
