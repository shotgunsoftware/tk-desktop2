# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import time
import sgtk
from sgtk.platform.qt import QtCore, QtGui
from .deferred_request import DeferredRequest
from ... import constants

logger = sgtk.LogManager.get_logger(__name__)
external_config = sgtk.platform.import_framework(
    "tk-framework-shotgunutils", "external_config"
)


class RequestRunner(QtCore.QObject):
    """
    Execution engine for websockets requests (objects deriving
    from :class:`WebsocketsRequest`. Objects are registered via the
    `execute` method and will be queued up for execution.

    Some commands can be executed immediately, others need to have
    async work carried out before they can be executing.
    """

    def __init__(self, engine_instance_name, plugin_id, base_config, task_manager):
        """
        :param str engine_instance_name: The instance name of the engine for
            which we should be retrieving commands.
        :param str plugin_id: The plugin id associated with the runtime environment.
        :param str base_config: Descriptor URI for the config to use by default when
            no custom pipeline configs have been defined in Shotgun.
        :param task_manager: Task Manager to use for async processing.
        """
        qt_parent = QtCore.QCoreApplication.instance()

        super(RequestRunner, self).__init__(qt_parent)

        logger.debug("Begin initializing RequestRunner")
        logger.debug("Engine instance name: %s" % engine_instance_name)
        logger.debug("Plugin id: %s" % plugin_id)
        logger.debug("Base config: %s" % base_config)
        self._bundle = sgtk.platform.current_bundle()

        # caching of configurations in memory
        self._cached_configs = {}
        self._last_update_check = 0

        # list of active websockets requests
        self._active_requests = []

        # hook up external configuration loader
        self._config_loader = external_config.ExternalConfigurationLoader(
            self._bundle.python_interpreter_path,
            engine_instance_name,
            plugin_id,
            base_config,
            task_manager,
            qt_parent,
        )
        self._config_loader.configurations_loaded.connect(
            self._on_configurations_loaded
        )
        self._config_loader.configurations_changed.connect(
            self._on_configurations_changed
        )

    def execute(self, request):
        """
        Registers a websockets request for processing.
        Some commands may run asynchronous.

        :param request: :class:`WebsocketsRequest` instance to execute.
        """
        # log analytics
        if request.analytics_command_name:
            bundle = sgtk.platform.current_bundle()
            self._bundle.log_metric(
                "Executed websockets command",
                command_name=request.analytics_command_name,
            )

        if not request.requires_toolkit:
            # no toolkit context needed. Action straight away.
            request.execute()
            return

        # for toolkit requests, wrap them in a deferred request and
        # asynchronously collect all the configuration parts
        # needed to process them.

        # add it to list for processing
        deferred_request = DeferredRequest(request)
        self._active_requests.append(deferred_request)

        # request its associated configurations
        if deferred_request.project_id in self._cached_configs:
            logger.debug("Configurations cached in memory.")
            # we got the configs cached!
            # ping a check to check that Shotgun pipeline configs are up to date
            cache_out_of_date = (
                time.time() - self._last_update_check
            ) > constants.CONFIG_CHECK_TIMEOUT_SECONDS
            if cache_out_of_date:
                # time to check with Shotgun if there are updates
                logger.debug(
                    "Requesting a check to see if any changes have happened in Shotgun."
                )
                self._last_update_check = time.time()
                # refresh - this may trigger a call to _on_configurations_changed
                self._config_loader.refresh_shotgun_global_state()

            # request command for the configurations
            deferred_request.register_configurations(
                self._cached_configs[deferred_request.project_id]
            )
            for config in self._cached_configs[deferred_request.project_id]:
                config.request_commands(
                    deferred_request.project_id,
                    deferred_request.entity_type,
                    deferred_request.entity_id,
                    deferred_request.linked_entity_type,
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
            logger.debug(
                "Requesting new configurations for %s." % deferred_request.project_id
            )
            self._config_loader.request_configurations(deferred_request.project_id)

    def _on_configurations_loaded(self, project_id, configs):
        """
        Called when external configurations for the given project have been loaded.

        :param int project_id: Project id that configurations are associated with
        :param list configs: List of class:`ExternalConfiguration` instances belonging to the
            project_id.
        :param typle error: If an error occurred when loading configurations, the
            tuple will contain the error message and traceback, in that order.
        """
        # NOTE: To maintain behavior with the older browser integration provided
        # by the desktopserver framework, if any of the configurations are invalid,
        # we will raise an error back to the web app so that the error will be
        # seen by the user. The reason we do this is that the web app currently
        # has two states in the Toolkit actions menu: complete success and complete
        # failure. What we DON'T want to do is imply that everything is fine when
        # it isn't, so our best option is to mirror the old behavior and reply with
        # an error so the user sees it.
        invalid_configs = [c for c in configs if not c.is_valid]
        if invalid_configs:
            invalid_ids = [c.pipeline_configuration_id for c in invalid_configs]
            reason = "Cannot resolve configurations with the following ids: %s" % (
                invalid_ids,
            )
            logger.warning(reason)

            for deferred_request in self._active_requests:
                if deferred_request.project_id == project_id:
                    deferred_request.register_configurations(invalid_configs)
                    deferred_request.register_configurations_failure(
                        reason, invalid_configs
                    )

            self._execute_ready_requests()
            return

        logger.debug("New configs loaded for project id %s: %s" % (project_id, configs))

        # cache our configs
        self._cached_configs[project_id] = configs

        logger.debug(
            "Config interpreter paths will be updated to: %s",
            self._bundle.python_interpreter_path
        )

        # wire up signals from our cached command objects
        for config in configs:
            # SG Create's Python interpreter path changes after the application is updated.
            # we need to ensure that our path isn't stale, as it might have been cached
            # to disk before the most recent update.
            config.interpreter = self._bundle.python_interpreter_path
            config.commands_loaded.connect(self._on_commands_loaded)
            config.commands_load_failed.connect(self._on_commands_load_failed)

        # for all active requests, request commands to be loaded
        for deferred_request in self._active_requests:
            if deferred_request.project_id == project_id:
                deferred_request.register_configurations(configs)
                for config in configs:
                    config.request_commands(
                        project_id,
                        deferred_request.entity_type,
                        deferred_request.entity_id,
                        deferred_request.linked_entity_type,
                    )

    def _on_commands_loaded(
        self, project_id, entity_type, entity_id, link_entity_type, config, commands
    ):
        """
        Called when commands have been loaded for a given configuration.

        Note that this may be called several times for a project, if the project
        has got several pipeline configurations (for example dev sandboxes).

        :param int project_id: Project id associated with the request.
        :param str entity_type: Entity type associated with the request.
        :param int entity_id: Entity id associated with the request.
        :param str link_entity_type: Linked entity type associated with the request.
        :param config: Associated class:`ExternalConfiguration` instance.
        :param list commands: List of :class:`ExternalCommand` instances.
        """
        logger.debug(
            "%s commands loaded for project id %s, %s"
            % (len(commands), project_id, config)
        )

        # SG Create's Python interpreter path will change when the application
        # is updated. This necessitates making sure we set the correct interpreter
        # after loading cached commands, because they might have been cached to
        # disk before the most recent update of SG Create.
        #
        # NOTE: we know there's an underlying problem here and that we have more
        # work to do in the future before we can bake Create's Python interpreter
        # into advanced config setups. Because it changes during an update, the
        # path referenced in a config will also have to update along with it. We
        # have the beginnings of a plan in place where we will reference a manifest
        # that directs us to a Python interpreter path that is current, and we'll
        # need to follow that when Toolkit is referencing the Python path. The
        # beginnings of that work is done (the manifest file exists now), but
        # we aren't quite ready to do the rest of the work required.
        logger.debug(
            "Command interpreter paths will be updated to: %s",
            self._bundle.python_interpreter_path
        )

        for command in commands:
            command.interpreter = self._bundle.python_interpreter_path

        for deferred_request in self._active_requests:
            if (
                deferred_request.project_id == project_id
                and deferred_request.entity_type == entity_type
            ):
                deferred_request.register_commands(config, commands)

        # kick off any requests that are waiting
        self._execute_ready_requests()

    def _on_commands_load_failed(
        self, project_id, entity_type, entity_id, link_entity_type, config, reason
    ):
        """
        Called when commands have been loaded for a given configuration.

        Note that this may be called several times for a project, if the project
        has got several pipeline configurations (for example dev sandboxes).

        :param int project_id: Project id associated with the request.
        :param str entity_type: Entity type associated with the request.
        :param int entity_id: Entity id associated with the request.
        :param str link_entity_type: Linked entity type associated with the request.
        :param config: Associated class:`ExternalConfiguration` instance.
        :param str reason: Details around the failure.
        """
        logger.debug(
            "Loading commands failed for project id %s, %s" % (config, project_id)
        )
        for deferred_request in self._active_requests:
            if (
                deferred_request.project_id == project_id
                and deferred_request.entity_type == entity_type
            ):
                deferred_request.register_commands_failure(config, reason)

        # kick off any requests that are waiting
        self._execute_ready_requests()

    def _execute_ready_requests(self):
        """
        Execute all requests which have a well defined state and thus
        are ready for execution. Remove them from the internal
        list of active requests.
        """
        logger.debug("Preparing ready requests for execution...")
        remaining_requests = []
        for deferred_request in self._active_requests:
            if deferred_request.can_be_executed():
                # fire off!
                deferred_request.execute()
            else:
                remaining_requests.append(deferred_request)

        logger.debug("There are now %s pending requests." % len(remaining_requests))
        self._active_requests = remaining_requests
