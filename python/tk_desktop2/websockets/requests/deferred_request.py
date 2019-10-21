# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import sgtk
import copy
from sgtk.platform.qt import QtCore, QtGui

logger = sgtk.LogManager.get_logger(__name__)


class DeferredRequest(object):
    """
    Wrapper around a :class:`WebsocketsRequest` which serves as a broker between
    the request runner and the :class:`WebsocketsRequest`.

    Certain websocket commands require a full state of commands and configurations
    prior to execution. The external_config interface which is part of shotgunutils
    is fully asynchronous and will provide any external data as soon as it has
    access to it.

    This class provides a buffer which builds up a full configuration state so that
    Toolkit WebsocketsRequest are only executed once a full external state, covering
    all different pipeline configurations, has been loaded.
    """

    def __init__(self, request):
        """
        :param request: :class:`WebsocketsRequest` to wrap around.
        """
        self._request = request
        self._configurations = None

    @property
    def project_id(self):
        """
        Project id associated with this request
        """
        return self._request.project_id

    @property
    def entity_type(self):
        """
        Entity type associated with this request
        """
        return self._request.entity_type

    @property
    def entity_id(self):
        """
        Entity id associated with this request or None for a general request
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
    def analytics_command_name(self):
        """
        The command name to pass to analytics or None if no value should be logged.
        """
        return self._request.analytics_command_name

    def can_be_executed(self):
        """
        True if the request is ready to be executed, false if not
        """
        if self._configurations:
            # a set of configurations have been loaded in but
            # we are still waiting for them to load in their
            # individual commands.
            #
            # each configuration entry in the self._configurations
            # list is a dictionary with three keys:
            # - configuration - associated ExternalConfiguration instance
            # - commands - list of ExternalCommand instances or None if error
            # - error - error string or None if commands loaded
            #
            # now check if all configurations have completed loading
            #
            for config in self._configurations:
                # a loaded config either has a list of commands or an error message
                if config["commands"] is None and config["error"] is None:
                    return False
            # all items loaded
            return True
        else:
            # config not yet loaded
            return False

    def execute(self):
        """
        Execute the request

        :raises: :class:`RuntimeError` on failure.
        """
        if not self.can_be_executed():
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
        """
        Registers a list of configurations with the instance.

        :param configs: List of :class:`ExternalConfiguration` objects.
        """
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
                {"configuration": config, "commands": None, "error": None}
            )

    def register_configurations_failure(self, reason, invalid_configs):
        """
        Registers that configurations for the project could not be loaded.

        :param str reason: Error message.
        :param list invalid_configs: A list of invalid :class:`ExternalConfiguration` objects
            that were found.
        """
        logger.debug(
            "Configuration loading failed (project_id=%s): %s"
            % (self.project_id, reason)
        )

        for config_dict in self._configurations:
            if config_dict["configuration"] in invalid_configs:
                config_dict["commands"] = None
                config_dict["error"] = reason
                break

    def register_commands(self, config, commands):
        """
        Registers the commands for a given external configuration.

        :param config: Associated :class:`ExternalConfiguration` object.
        :param list commands: List of associated :class:`ExternalCommand` objects.
        """
        logger.debug("Register commands for config %s" % config)
        for config_dict in self._configurations:
            if config_dict["configuration"] == config:
                config_dict["commands"] = copy.copy(commands)
                config_dict["error"] = None
                break

    def register_commands_failure(self, config, reason):
        """
        Registers that a configuration could not be loaded.

        :param config: Associated :class:`ExternalConfiguration` object.
        :param str reason: Error message.
        """
        logger.debug("Register commands failed for config %s: %s" % (config, reason))
        for config_dict in self._configurations:
            if config_dict["configuration"] == config:
                config_dict["commands"] = None
                config_dict["error"] = reason
                break
