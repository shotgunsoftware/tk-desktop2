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


class OpenVersionInSGCreateWebsocketsRequest(WebsocketsRequest):
    """
    """
    def __init__(self, connection, id, parameters):
        """
        :param connection: Associated :class:`WebsocketsConnection`.
        :param int id: Id for this request.
        :param bool pick_multiple: Flag to indicate whether multi select should be enabled.
        """
        self._params = parameters
        super(OpenVersionInSGCreateWebsocketsRequest, self).__init__(connection, id)

    def execute(self):
        """
        
        """

        try:
            logger.error("EXECUTE OPEN VERSION!")
        except Exception as e:
            self._reply_with_status(
                status=1,
                error=str(e)
            )
        else:
            self._reply_with_status(0)
