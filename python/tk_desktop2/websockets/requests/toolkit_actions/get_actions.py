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
from ..base import WebsocketsRequest

logger = sgtk.LogManager.get_logger(__name__)


class GetActionsWebsocketsRequest(WebsocketsRequest):
    """
    Request:

        {
            'entity_id': 111,
            'entity_type': 'Shot',
            'project_id': 584,
            'user': {
                'entity': {
                    'id': 42,
                    'name': 'John Smith',
                    'status': 'act',
                    'type': 'HumanUser',
                    'valid': 'valid'
                    },
               'group_ids': [3],
               'rule_set_display_name': 'Admin',
               'rule_set_id': 5
            }
        },

    Response on success:

    {
        retcode:0,
        actions: {
            "Primary: {
                "config": "Primary",
                "actions": [ <ACTION>, <ACTION>, ...]
            },

            "Dev": {
                "config": "Primary",
                "actions": [ <ACTION>, <ACTION>, ...]
            }
        },
        pcs:["Primary", "Dev"], # list of pipeline configuration names
    }

    Where <ACTION> is a dictionary on the following form:

    {
        name: command_name,
        title: title to appear in UI
        deny_permissions: [] # list of permission roles for this not to show up. legacy.
        app_name: tk-multi-launchapp
        group: Group Name
        group_default: False
        engine_name: tk-desktop2
    }

    Response to indicate that we are loading:

        {
            retcode=1
        }

    Response to indicate that an unsupported entity type has been requested:

        {
            retcode=2
        }

    # both of the above are legacy and we shouldn't send them back

    Other errors:

        {
            retcode=?
            out='Error message'
            err='' # left blank
        }
    """

    # RPC return codes.
    SUCCESSFUL_LOOKUP = 0
    CACHING_NOT_COMPLETED = 1
    UNSUPPORTED_ENTITY_TYPE = 2
    CACHING_ERROR = 3

    def __init__(self, connection, id, parameters):
        super(GetActionsWebsocketsRequest, self).__init__(connection, id)

        if "entity_id" not in parameters:
            raise ValueError("%s: Missing entity_id in parameters." % self)

        if "entity_type" not in parameters:
            raise ValueError("%s: Missing entity_type in parameters." % self)

        if "project_id" not in parameters:
            raise ValueError("%s: Missing project_id in parameters." % self)

        self._entity_id = parameters["entity_id"]
        self._entity_type = parameters["entity_type"]
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
        Project id associated with this request or None for a site wide request
        """
        return self._project_id

    @property
    def entity_type(self):
        """
        Entity type associated with this request or None for a site wide request
        """
        return self._entity_type

    @property
    def entity_id(self):
        """
        Entity id associated with this request or None for a site wide request
        """
        return self._entity_id

    @property
    def linked_entity_type(self):
        """
        Linked entity type associated with this request or None if not applicable.
        Linked entity types are useful to distinguish for example a configuration
        difference between tasks linked to shots vs tasks linked to assets.
        """
        return None

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

        # first detect if any configuration loaded with errors.
        # in that case, send an error for the entire group
        # TODO: can this be handled in a better way? How is it done today?
        errors = []
        for config in associated_commands:
            if config["error"]:
                errors.append(config["error"])

        if len(errors) > 0:
            self._reply({
                "retcode": self.CACHING_ERROR,
                "err": "\n".join(errors)
            })
            return





    # {
    #     retcode:0,
    #     actions: {
    #         "Primary: {
    #             "config": "Primary",
    #             "actions": [ <ACTION>, <ACTION>, ...]
    #         },
    #
    #         "Dev": {
    #             "config": "Primary",
    #             "actions": [ <ACTION>, <ACTION>, ...]
    #         }
    #     },
    #     pcs:["Primary", "Dev"], # list of pipeline configuration names
    # }

        response = {
            "retcode": 0,
            "pcs": [],
            "actions": {}
        }

        # {
        #     name: command_name,
        #     title: title to appear in UI
        #     deny_permissions: []  # list of permission roles for this not to show up. legacy.
        #     app_name: tk - multi - launchapp
        #     group: Group Name
        #     group_default: False
        # engine_name: tk - desktop2
        # }


        for config in associated_commands:
            config_name = config["configuration"].pipeline_configuration_name

            if config_name is None:
                # this is a zero config setup with no record in Shotgun
                config_name = "Primary"

            response["pcs"].append(config_name)

            # figure out the actions
            actions = []
            for command in config["commands"]:
                actions.append({
                    "name": command.serialize(),
                    "title": command.display_name,
                    "deny_permissions": [],
                    "app_name": "",
                    "group": "",
                    "group_default": False,
                    "engine_name": ""
                })

            response["actions"][config_name] = {
                "config": config_name,
                "actions": actions,
            }



        self._reply(response)




