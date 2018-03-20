# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import sys
import time
import sgtk
import json
import datetime

from .deferred_request import DeferredRequest

from sgtk.platform.qt import QtCore, QtGui

logger = sgtk.LogManager.get_logger(__name__)

external_config = sgtk.platform.import_framework("tk-framework-shotgunutils", "external_config")


class RequestRunner(QtCore.QObject):
    """
    Executes websockets Request objects
    """

    CONFIG_CHECK_TIMEOUT_SECONDS = 30

    def __init__(self, engine_instance_name, plugin_id, base_config, task_manager):
        """
        Start up the engine's built in request runner

        :param str engine_instance_name: The instance name of the engine for
            which we should be retrieving commands.
        :param str plugin_id: The plugin id associated with the runtime environment.
        :param str base_config: Descriptor URI for the config to use by default when
            no custom pipeline configs have been defined in Shotgun.
        """
        qt_parent = QtCore.QCoreApplication.instance()

        super(RequestRunner, self).__init__(qt_parent)

        logger.debug("Begin initializing RequestRunner")
        logger.debug("Engine instance name: %s" % engine_instance_name)
        logger.debug("Plugin id: %s" % plugin_id)
        logger.debug("Base config: %s" % base_config)

        # caching of configurations in memory
        self._cached_configs = {}
        self._last_update_check = 0

        # list of active websockets requests
        self._active_requests = []

        # hook up external configuration loader
        self._config_loader = external_config.ExternalConfigurationLoader(
            self._get_python_interpreter_path(),
            engine_instance_name,
            plugin_id,
            base_config,
            task_manager,
            qt_parent
        )
        self._config_loader.configurations_loaded.connect(self._on_configurations_loaded)
        self._config_loader.configurations_changed.connect(self._on_configurations_changed)

    def _get_python_interpreter_path(self):
        """
        Returns the path to the desktop2 python interpreter

        :returns: Path to python
        """
        # TODO: centralize and fix
        if sys.platform == "win32":
            return os.path.abspath(os.path.join(sys.prefix, "python.exe"))
        else:
            return os.path.abspath(os.path.join(sys.prefix, "bin", "python"))

    def execute(self, request):
        """
        Registers a websockets request for asynchronous proceessing.
        """
        if not request.requires_toolkit:
            # no toolkit context needed. Action straight away.
            request.execute()
            return

        # for toolkit requests, wrap them in a deferred request and
        # asynchronounsly collect all the configuration parts
        # needed to process them.

        # add it to list for processing
        deferred_request = DeferredRequest(request)
        self._active_requests.append(deferred_request)

        # request its associated configurations
        if deferred_request.project_id in self._cached_configs:
            logger.debug("Configurations cached in memory.")
            # we got the configs cached!
            # ping a check to check that Shotgun pipeline configs are up to date
            cache_out_of_date = (time.time() - self._last_update_check) > self.CONFIG_CHECK_TIMEOUT_SECONDS
            if cache_out_of_date:
                # time to check with Shotgun if there are updates
                logger.debug("Requesting a check to see if any changes have happened in Shotgun.")
                self._last_update_check = time.time()
                # refresh - this may trigger a call to _on_configurations_changed
                self._config_loader.refresh_shotgun_global_state()

            # request command for the conifgurations
            deferred_request.register_configurations(
                self._cached_configs[deferred_request.project_id]
            )
            for config in self._cached_configs[deferred_request.project_id]:
                config.request_commands(
                    deferred_request.project_id,
                    deferred_request.entity_type,
                    deferred_request.entity_id,
                    deferred_request.linked_entity_type
                )

        else:
            logger.debug(
                "No configurations cached. "
                "Requesting configuration data for project %s" % request.project_id
            )
            # we don't have any configuration objects cached yet.
            # request it - _on_configurations_loaded will be triggered when configurations are loaded
            self._config_loader.request_configurations(request.project_id)

    def _on_configurations_changed(self):
        """
        Indicates that the state of Shotgun has changed
        and that we should discard any cached configurations and reload them.
        """
        logger.debug(
            "Shotgun has changed. "
            "Requesting configuration reloads for all active requests."
        )

        for deferred_request in self._active_requests:
            logger.debug("Requesting new configurations for %s." % deferred_request.project_id)
            self._config_loader.request_configurations(deferred_request.project_id)

    def _on_configurations_loaded(self, project_id, configs):
        """
        Called when external configurations for the given project have been loaded.

        :param int project_id: Project id that configurations are associated with
        :param list configs: List of ExternalConfiguration instances belonging to the
            project_id.
        """
        logger.debug(
            "New configs loaded for project %s: %s" % (project_id, configs)
        )

        # cache our configs
        self._cached_configs[project_id] = configs

        # wire up signals from our cached command objects
        for config in configs:
            config.commands_loaded.connect(self._on_commands_loaded)
            config.commands_load_fail.connect(self._on_commands_load_failed)

        # for all active requests, request commands to be loaded
        for deferred_request in self._active_requests:
            if deferred_request.project_id == project_id:
                deferred_request.register_configurations(configs)
                for config in configs:
                    config.request_commands(
                        project_id,
                        deferred_request.entity_type,
                        deferred_request.entity_id,
                        deferred_request.linked_entity_type
                    )

    def _on_commands_loaded(self, project_id, config, commands):
        """
        Called when commands have been loaded for a given configuration.

        Note that this may be called several times for a project, if the project
        has got several pipeline configurations (for example dev sandboxes).

        :param int project_id: Project id associated with the request.
        :param config: Associated ExternalConfiguration instance.
        :param list commands: List of ExternalCommand instances.
        """
        logger.debug("%s Commands loaded for projecd id %s, %s" % (len(commands), project_id, config))
        for deferred_request in self._active_requests:
            if deferred_request.project_id == project_id:
                deferred_request.register_commands(config, commands)

        # kick off any requests that are waiting
        self._execute_ready_requests()

    def _on_commands_load_failed(self, project_id, config, reason):
        """
        Called when commands have been loaded for a given configuration.

        Note that this may be called several times for a project, if the project
        has got several pipeline configurations (for example dev sandboxes).

        :param int project_id: Project id associated with the request.
        :param config: Associated ExternalConfiguration instance.
        :param str reason: Details around the failure.
        """
        logger.debug("Loading commmands failed for project id %s, %s" % (config, project_id))
        for deferred_request in self._active_requests:
            if deferred_request.project_id == project_id:
                deferred_request.register_commands_failure(config, reason)

        # kick off any requests that are waiting
        self._execute_ready_requests()

    def _execute_ready_requests(self):
        """

        """
        logger.debug("Preparing ready requests for execution...")
        remaining_requests = []
        for deferred_request in self._active_requests:
            if deferred_request.can_be_executed:
                # fire off!
                deferred_request.execute()
            else:
                remaining_requests.append(deferred_request)

        logger.debug("There are now %s pending requests." % len(remaining_requests))
        self._active_requests = remaining_requests

