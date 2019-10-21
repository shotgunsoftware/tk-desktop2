# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import sgtk
import sys
import os
import threading
from sgtk.util.process import subprocess_check_output, SubprocessCalledProcessError
from ..request import WebsocketsRequest

logger = sgtk.LogManager.get_logger(__name__)


class OpenFileWebsocketsRequest(WebsocketsRequest):
    """
    Websockets command to open the given file in an associated environment.
    Part of the local file linking feature set.

    Request syntax::

        {'filepath': '/path/to/file.mov',
         'user': {'entity': {'id': 42,
                          'name': 'John Smith',
                          'status': 'act',
                          'type': 'HumanUser',
                          'valid': 'valid'},
               'group_ids': [3],
               'rule_set_display_name': 'Admin',
               'rule_set_id': 5}},

    Expected response::

        A single boolean, indicating if the open succeeded, false if not.

    The following methods will be used to open the file:

    - Linux:   Launch 'xdg-open <path>'
    - Mac:     Launch 'open <path>'
    - Windows: Launch via the os.startfile API.

    If an environment variable SHOTGUN_PLUGIN_LAUNCHER is specified,
    this will override the default launch command described above.
    """

    def __init__(self, connection, id, parameters):
        """
        :param connection: Associated :class:`WebsocketsConnection`.
        :param int id: Id for this request.
        :param dict parameters: Command parameters (see syntax above)
        :raises: ValueError
        """
        super(OpenFileWebsocketsRequest, self).__init__(connection, id)

        if sys.platform.startswith("linux"):
            self._launcher = "xdg-open"
        elif sys.platform == "darwin":
            self._launcher = "open"
        elif sys.platform == "win32":
            self._launcher = None

        if os.environ.get("SHOTGUN_PLUGIN_LAUNCHER"):
            self._launcher = os.environ.get("SHOTGUN_PLUGIN_LAUNCHER")
            logger.debug("Using custom SHOTGUN_PLUGIN_LAUNCHER '%s'" % self._launcher)

        if "filepath" not in parameters:
            raise ValueError("%s: Missing 'filepath' parameter" % self)

        self._path = parameters["filepath"]

    @property
    def analytics_command_name(self):
        """
        The command name to pass to analytics.
        """
        return "local_file_linking_open_file"

    def _execute(self):
        """
        Execute payload in a separate thread.

        :raises: RuntimeError
        """
        if not os.path.exists(self._path):
            raise RuntimeError("Error opening path [%s]. Path not found." % self._path)

        try:
            if self._launcher is None:
                os.startfile(self._path)
            else:
                subprocess_check_output([self._launcher, self._path])
        except SubprocessCalledProcessError as e:
            logger.debug("Error opening path [%s].", exc_info=True)
            self._reply_with_status(status=e.returncode, error=e.output)
        except Exception as e:
            self._reply_with_status(status=1, error=str(e))
        else:
            # operation succeeded. Reply with single boolean.
            self._reply(True)

    def execute(self):
        """
        Non-blocking execution.
        """
        worker = threading.Thread(target=self._execute)
        worker.daemon = True
        worker.start()
