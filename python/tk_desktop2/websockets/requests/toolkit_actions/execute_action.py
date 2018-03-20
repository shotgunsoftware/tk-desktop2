    # Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import sgtk
import json
import pprint
import datetime
import threading
from ..base import WebsocketsRequest

logger = sgtk.LogManager.get_logger(__name__)

external_config = sgtk.platform.import_framework("tk-framework-shotgunutils", "external_config")

class ExecuteActionWebsocketsRequest(WebsocketsRequest):
    """
        { 'entity_ids': [582],
          'entity_type': 'Project',
          'name': '',
          'pc': 'Primary',
          'pc_root_path': '',
          'project_id': 582,
          'title': 'Maya 2017',
          'user': {'entity': {'id': 42,
                              'name': 'Manne \xc3\x96hrstr\xc3\xb6m',
                              'status': 'act',
                              'type': 'HumanUser',
                              'valid': 'valid'},
                   'group_ids': [3],
                   'rule_set_display_name': 'Admin',
                   'rule_set_id': 5}},
          },


    """


    def __init__(self, connection, id, parameters):
        super(ExecuteActionWebsocketsRequest, self).__init__(connection, id)
        self._command = external_config.ExternalCommand.deserialize(parameters["name"])

    @property
    def requires_toolkit(self):
        """
        True if the request requires toolkit
        """
        return True

    @property
    def project_id(self):
        """
        Project id associated with this request or None for a site wide request
        """
        return None

    @property
    def entity_type(self):
        """
        Entity type with this request or None for a site wide request
        """
        return None

    @property
    def entity_id(self):
        """
        Entity id with this request or None for a site wide request
        """
        return None

    def execute_with_context(self, configurations):
        """
        Executes the request. Passes a fully loaded external
        configuration state to aid execution, laid out in the following
        structure:

        [
            {
                "configuration": <ExternalConfiguration>,
                "commands": [<ExternalCommand>, ...],
                "error": None
            },
            {
                "configuration": <ExternalConfiguration>,
                "commands": None,
                "error": "Something went wrong"
            },
        ]

        :param list configurations: See above for details.
        """
        # execute external command in a thread to not block
        # main thread execution
        worker = threading.Thread(target=action.execute)
        # if the python environment shuts down, no need
        # to wait for this thread
        worker.daemon = True
        # launch external process
        worker.start()