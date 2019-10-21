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
    Websockets command to request a list of toolkit actions
    suitable for an entity or group of entities.

    Request syntax::

        Requesting actions for a particular object:
        {
            'entity_id': 111,
            'entity_type': 'Shot',
            'project_id': 584,
            'user': {...}
            }
        }

        Requesting generic actions for assets:
        {
            'entity_id': -1, # part of the shotgun protocol
            'entity_type': 'Asset',
            'project_id': 584,
            'user': {...}
            }
        }

    Expected response::

        {
            "retcode": 0,
            "actions": {
                "Primary: {
                    "config": "Primary",
                    "actions": [ <ACTION>, <ACTION>, ...]
                },

                "Dev": {
                    "config": "Primary",
                    "actions": [ <ACTION>, <ACTION>, ...]
                }
            },
            "pcs": ["Primary", "Dev"], # list of pipeline configuration names
        }

        Where <ACTION> is a dictionary on the following form:

        {
            "name": "command_name",
            "title": "title to appear in UI"
            "deny_permissions": [] # list of permission roles for this not to show up.
            "app_name": "tk-multi-launchapp"
            "group": "Group Name"
            "group_default": False
            "engine_name": "tk-desktop2"
        }

    Response that we are loading (legacy syntax, not supported by this class)::

        {
            "retcode": 1
        }

    Response to indicate that an unsupported entity type has
    been requested (legacy syntax, not supported by this class)::

        {
            "retcode": 2
        }
    """

    # RPC return codes.
    SUCCESSFUL_LOOKUP = 0
    CACHING_NOT_COMPLETED = 1  # legacy
    UNSUPPORTED_ENTITY_TYPE = 2  # legacy
    CACHING_ERROR = 3

    def __init__(self, connection, id, parameters):
        """
        :param connection: Associated :class:`WebsocketsConnection`.
        :param int id: Id for this request.
        :param dict parameters: Command parameters (see syntax above)
        """
        super(GetActionsWebsocketsRequest, self).__init__(connection, id)

        self._bundle = sgtk.platform.current_bundle()

        # note - parameter data is coming in from javascript so we
        #        perform some in-depth validation of the values
        #        prior to blindly accepting them.
        required_params = ["entity_id", "entity_type", "project_id"]
        for required_param in required_params:
            if required_param not in parameters:
                raise ValueError(
                    "%s: Missing parameter '%s' in payload." % (self, required_param)
                )

        self._entity_id = parameters["entity_id"]
        self._entity_type = parameters["entity_type"]
        self._project_id = parameters["project_id"]
        self._linked_entity_type = None

        # if command specifies a -1 for the entity id
        # this is a request for a generic set of actions
        # for an entity of that type. Change it to be
        # entity id None for our request handler to indicate this.
        if self._entity_id == -1:
            self._entity_id = None

        # if we are looking at a task, figure out the type of
        # the associated item.
        # TODO - this could easily be passed down by the
        # websockets protocol as a performance improvement.
        if self._entity_type == "Task" and self._entity_id:
            logger.debug("Resolving linked entity for Task %s...", self._entity_id)
            sg_data = self._bundle.shotgun.find_one(
                "Task", [["id", "is", self._entity_id]], ["entity"]
            )
            logger.debug("Task is linked with %s", sg_data)
            if sg_data["entity"]:
                self._linked_entity_type = sg_data["entity"]["type"]

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
        return self._linked_entity_type

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
        errors = []
        for command in associated_commands:
            if command["error"]:
                errors.append(command["error"])

        if len(errors) > 0:
            self._reply_with_status(status=self.CACHING_ERROR, error="\n".join(errors))
            return

        # compile response
        response = {"retcode": 0, "pcs": [], "actions": {}}

        for config in associated_commands:

            # this is a zero config setup with no record in Shotgun
            # such a config is expected to be named Primary in Shotgun
            config_name = (
                config["configuration"].pipeline_configuration_name or "Primary"
            )

            response["pcs"].append(config_name)

            # figure out the actions
            actions = []
            for command in config["commands"]:
                actions.append(
                    {
                        "name": command.system_name,
                        "title": command.display_name,
                        "deny_permissions": command.excluded_permission_groups_hint,
                        "app_name": "UNSPECIFIED",  # legacy
                        "group": command.group,
                        "group_default": command.is_group_default,
                        "engine_name": "UNSPECIFIED",  # legacy
                        "supports_multiple_selection": command.support_shotgun_multiple_selection,
                    }
                )

            response["actions"][config_name] = {
                "config": config_name,
                "actions": actions,
            }

        self._reply(response)
