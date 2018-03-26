# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import sgtk
from ..request import WebsocketsRequest

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

        When loading a page of assets:
        {'command': {'data': {'entity_id': -1,
                              'entity_type': 'Asset',
                              'project_id': 595,
                              'user': {'entity': {'id': 42,
                                                  'name': 'Manne \xc3\x96hrstr\xc3\xb6m',
                                                  'status': 'act',
                                                  'type': 'HumanUser',
                                                  'valid': 'valid'},
                                       'group_ids': [3],
                                       'rule_set_display_name': 'Admin',
                                       'rule_set_id': 5}},
                     'name': 'get_actions'},
         'id': 2,
         'protocol_version': 2,
         'timestamp': 1521627818184}


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

        # validate parameters
        required_params = [
            "entity_id",
            "entity_type",
            "project_id"
        ]
        for required_param in required_params:
            if required_param not in parameters:
                raise ValueError("%s: Missing parameter '%s' in payload." % (self, required_param))

        self._entity_id = parameters["entity_id"]
        self._entity_type = parameters["entity_type"]
        self._project_id = parameters["project_id"]

        # if command specifies a -1 for the entity id
        # this is a request for a generic set of actions
        # for an entity of that type. Change it to be
        # entity id None for our request handler to indicate this.
        if self._entity_id == -1:
            self._entity_id = None


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
        Entity id associated with this request or None for a general request
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
                    "name": command.system_name,
                    "title": command.display_name,
                    "deny_permissions": command.excluded_permission_groups_hint,
                    "app_name": "UNSPECIFIED",
                    "group": command.group,
                    "group_default": command.is_group_default,
                    "engine_name": "UNSPECIFIED"
                })

            response["actions"][config_name] = {
                "config": config_name,
                "actions": actions,
            }



        self._reply(response)




