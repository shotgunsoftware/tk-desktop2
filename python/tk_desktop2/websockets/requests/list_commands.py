# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import sgtk
from .request import WebsocketsRequest
from .commands import get_supported_commands

logger = sgtk.LogManager.get_logger(__name__)


class ListSupportedCommandsWebsocketsRequest(WebsocketsRequest):
    """
    Websockets command to list the commands that are supported
    by this websockets server.

    Expected response::

        A list of strings with command names.
    """

    def __init__(self, connection, id, parameters):
        """
        :param connection: Associated :class:`WebsocketsConnection`.
        :param int id: Id for this request.
        :param dict parameters: Command parameters (see syntax above)
        :raises: ValueError
        """
        super(ListSupportedCommandsWebsocketsRequest, self).__init__(connection, id)

    def execute(self):
        """
        Command execution.
        """
        commands = get_supported_commands()
        self._reply(commands.keys())
