# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import sgtk
import threading
from ..request import WebsocketsRequest

logger = sgtk.LogManager.get_logger(__name__)

external_config = sgtk.platform.import_framework(
    "tk-framework-shotgunutils",
    "external_config"
)


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

        # validate parameters
        required_params = [
            "name",
            "title",
            "pc",
            "entity_ids",
            "entity_type",
            "project_id"
        ]
        for required_param in required_params:
            if required_param not in parameters:
                raise ValueError("%s: Missing parameter '%s' in payload." % (self, required_param))

        self._resolved_command = None
        self._command_name = parameters["name"]
        self._command_title = parameters["title"]
        self._config_name = parameters["pc"]
        self._entity_type = parameters["entity_type"]
        self._entity_id = parameters["entity_ids"][0]  # TODO: support multi select
        self._project_id = parameters["project_id"]

    @property
    def requires_toolkit(self):
        """
        True if the request requires toolkit
        """
        return True

    @property
    def project_id(self):
        """
        Project id associated with this request
        """
        return self._project_id

    @property
    def entity_type(self):
        """
        Entity type associated with this request
        """
        return self._entity_type

    @property
    def entity_id(self):
        """
        Entity id associated with this request
        """
        return self._entity_id

    def _execute(self):
        try:
            output = self._resolved_command.execute()
            self._reply({"retcode": 0, "out": output})
        except Exception as e:
            # todo : handle error
            self._reply({"retcode": -1, "err": str(e)})
            pass

    def execute_with_context(self, associated_commands):
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

        :param list associated_commands: See above for details.
        """
        # todo - handle multiple selections
        for config in associated_commands:

            config_name = config["configuration"].pipeline_configuration_name

            if config_name is None:
                # this is a zero config setup with no record in Shotgun
                config_name = "Primary"

            if config_name == self._config_name:
                for command in config["commands"]:
                    if command.system_name == self._command_name:
                        self._resolved_command = command
                        break

        if not self._resolved_command:
            raise RuntimeError("could not find ")

        # execute external command in a thread to not block
        # main thread execution
        worker = threading.Thread(target=self._execute)
        # if the python environment shuts down, no need
        # to wait for this thread
        worker.daemon = True
        # launch external process
        worker.start()
