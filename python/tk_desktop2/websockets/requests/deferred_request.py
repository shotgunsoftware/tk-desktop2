# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import os
import sys
import time
import sgtk
import json
import datetime

from sgtk.platform.qt import QtCore, QtGui

logger = sgtk.LogManager.get_logger(__name__)


class DeferredRequest(object):
    """
    Executes websockets Request objects
    """

    CONFIG_CHECK_TIMEOUT_SECONDS = 30

    def __init__(self, request):
        """
        """
        self._request = request
        self._configurations = None

    @property
    def project_id(self):
        """
        Project id associated with this request or None for a site wide request
        """
        return self._request.project_id

    @property
    def entity_type(self):
        """
        Entity type associated with this request or None for a site wide request
        """
        return self._request.entity_type

    @property
    def entity_id(self):
        """
        Entity id associated with this request or None for a site wide request
        """
        return self._request.entity_id

    @property
    def linked_entity_type(self):
        """
        Linked entity type associated with this request or None if not applicable.
        Linked entity types are useful to distinguish for example a configuration
        difference between tasks linked to shots vs tasks linked to assets.
        """
        return self._request.linked_entity_type

    @property
    def can_be_executed(self):
        """
        True if the request can be executed, false if not
        """
        if self._configurations:
            # have we got commands loaded for all configurations?
            for config in self._configurations:
                if config["commands"] is None and config["error"] is None:
                    # this entry has not been loaded yet
                    return False
            # all items loaded
            return True
        else:
            # config not yet loaded
            return False

    def execute(self):
        """
        Execute the request
        """
        if not self.can_be_executed:
            raise RuntimeError("%s is not ready to be executed!" % self)

        # put together a data structure to pass to the request
        # [
        #     {
        #         "configuration": <config>,
        #         "commands": [...],
        #         "error": None
        #     },
        #     {
        #         "configuration": <config>,
        #         "commands": None,
        #         "error": "Something went wrong"
        #     },
        # ]

        self._request.execute_with_context(self._configurations)

    def register_configurations(self, configs):
        logger.debug("%s: Register configurations %s" % (self, configs))

        # put together a data structure to hold the data and later
        # on pass it to the plugin
        # [
        #     {
        #         "configuration": <config>,
        #         "commands": [...],
        #         "error": None
        #     },
        #     {
        #         "configuration": <config>,
        #         "commands": None,
        #         "error": "Something went wrong"
        #     },
        # ]

        self._configurations = []
        for config in configs:
            self._configurations.append(
                {
                    "configuration": config,
                    "commands": [],
                    "error": None
                }
            )

    def register_commands(self, config, commands):
        logger.debug("Register commands for config %s" % config)
        for config_dict in self._configurations:
            if config_dict["configuration"] == config:
                config_dict["commands"] = commands
                config_dict["error"] = None


    def register_commands_failure(self, config, reason):
        logger.debug("Register commands failed for config %s: %s" % (config, reason))
        for config_dict in self._configurations:
            if config_dict["configuration"] == config:
                config_dict["commands"] = None
                config_dict["error"] = reason
