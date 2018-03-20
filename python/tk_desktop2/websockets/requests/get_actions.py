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
from .base import WebsocketsRequest

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

        err="",
        retcode=0,
        actions=all_actions,
        pcs=["Primary", "Dev"],

    Response on error:

        err="",
        retcode=0,
        actions=all_actions,
        pcs=config_names,

        err="Error message.",
        retcode=<non-zero>,
        out="Error summary",


    """

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

    def execute(self, configurations):
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
        raise NotImplementedError("WebsocketsRequest.execute not implemented by deriving class.")


            # actions = [
    #     dict(
    #         name="__core_info",
    #         title="Check for Core Upgrades...",
    #         deny_permissions=[],
    #         app_name="__builtin",
    #         group=None,
    #         group_default=False,
    #         engine_name="tk-shotgun",
    #     ),
    #
    #     dict(
    #         name="__core_info",
    #         title="Maya 2016",
    #         deny_permissions=[],
    #         app_name="__builtin",
    #         group="Launch Maya",
    #         group_default=False,
    #         engine_name="tk-shotgun",
    #     ),
    #
    #     dict(
    #         name="__core_info",
    #         title="Maya 2017",
    #         deny_permissions=[],
    #         app_name="__builtin",
    #         group="Launch Maya",
    #         group_default=True,
    #         engine_name="tk-shotgun",
    #     ),
    #
    # ]
    #
    # payload = {
    #     "err": "",
    #     "retcode": 0,
    #     "actions": {
    #         "Primary": {
    #             "config": "Primary",
    #             "actions": actions
    #         }
    #     },
    #     "pcs": ["Primary"],
    # }
    # return payload
