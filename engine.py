# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from sgtk.platform import Engine
import sgtk
import time

logger = sgtk.LogManager.get_logger(__name__)


class DesktopEngine2(Engine):
    """
    Toolkit Engine for Shotgun Desktop v2
    """
    # QObject name for the C++ actions model
    ACTION_MODEL_OBJECT_NAME = "ToolkitActionModel"

    # how often we check if shotgun configs have changed
    CONFIG_CHECK_TIMEOUT_SECONDS = 30

    # TODO - these constants should be passed down from the taap plugin
    # Engine instance name
    ENGINE_NAME = "tk-desktop2"
    # Configuration to load
    BASE_CONFIG = "sgtk:descriptor:app_store?name=tk-config-basic2"  # TODO - rename to tk-config-basic
    # Toolkit plugin id
    PLUGIN_ID = "basic.desktop2"

    def init_engine(self):
        """
        Main initialization entry point.
        """
        # list of cached configuration objects, keyed by projet id
        self._cached_configs = {}
        # last time stamp we checked for new configs.
        self._last_update_check = None
        # flag to indicate that the engine is running
        self._running_with_ui = False

    def post_app_init(self):
        """
        Initialization that runs after all apps and the QT abstractions have been loaded.
        """
        from sgtk.platform.qt import QtCore, QtGui

        fw = self.frameworks["tk-framework-shotgunutils"]
        external_config = fw.import_module("external_config")
        task_manager = fw.import_module("task_manager")
        shotgun_globals = fw.import_module("shotgun_globals")

        qt_parent = QtCore.QCoreApplication.instance()

        if qt_parent:
            self._running_with_ui = True

            # create a background task manager
            self._task_manager = task_manager.BackgroundTaskManager(
                qt_parent,
                start_processing=True,
                max_threads=2
            )

            # set it up with the shotgun globals
            shotgun_globals.register_bg_task_manager(self._task_manager)

            # todo - need to revisit this and sset up a proper dark theme for VMR intenrally.
            self._initialize_dark_look_and_feel()

            try:
                logger.debug("Attempting to bind against underlying C++ actions model...")
                self._actions_model = self._get_action_model()
            except RuntimeError:
                logger.error(
                    "Could not retrieve internal ActionModel interface. "
                    "No actions will be displayed."
                )
                self._actions_model = None
                self._command_handler = None
            else:
                # install signals from actions model
                self._actions_model.currentEntityPathChanged.connect(self._populate_context_menu)
                self._actions_model.actionTriggered.connect(self._execute_action)

                # hook up remote configuration loader
                self._command_handler = external_config.RemoteConfigurationLoader(
                    self.PLUGIN_ID,
                    self.BASE_CONFIG,
                    self._task_manager,
                    qt_parent
                )
                self._command_handler.configurations_loaded.connect(self._on_configurations_loaded)
                self._command_handler.configurations_changed.connect(self._on_configurations_changed)

    def _get_action_model(self):
        """
        Retrieves the internal C++ QT model that is used to render menus in Desktop2.

        :returns: QtoolkitActionsModel class (derived from QStandardItemModel)
        :raises: RuntimeError if not found
        """
        from sgtk.platform.qt import QtCore, QtGui
        for q_object in QtCore.QCoreApplication.instance().children():
            if q_object.objectName() == self.ACTION_MODEL_OBJECT_NAME:
                return q_object
                break
        raise RuntimeError("Could not retrieve internal object '%s'" % self.ACTION_MODEL_OBJECT_NAME)

    def _emit_log_message(self, handler, record):
        """
        Called by the engine whenever a new log message is available.

        :param handler: Log handler that this message was dispatched from
        :type handler: :class:`~python.logging.LogHandler`
        :param record: Std python logging record
        :type record: :class:`~python.logging.LogRecord`
        """
        # TODO - a console setup is pending design in VMR
        #        for now, just print to stdout
        print "[tk-desktop2] %s" % handler.format(record)

    def destroy_engine(self):
        """
        Engine shutdown.
        """
        logger.debug("Begin shutting down engine.")

        fw = self.frameworks["tk-framework-shotgunutils"]
        shotgun_globals = fw.import_module("shotgun_globals")

        try:
            if self._actions_model:
                # make sure that we release signals from the C++ object
                logger.debug("Disconnecting engine from internal actions model.")
                self._actions_model.currentEntityPathChanged.disconnect(self._populate_context_menu)
                self._actions_model.actionTriggered.disconnect(self._execute_action)
                self._actions_model = None

            if self._command_handler:
                logger.debug("Shutting down command handler interface.")
                self._command_handler.shut_down()

            # shut down main thread pool
            if self._task_manager:
                logger.debug("Stopping worker threads.")
                shotgun_globals.unregister_bg_task_manager(self._task_manager)
                self._task_manager.shut_down()

        except Exception, e:
            self.log_exception("Error running engine teardown logic")
        else:
            logger.debug("Engine shutdown complete.")

    def _path_to_entity(self, path):
        """
        Converts a desktop-2 style path to shotgun entities

        :param str path: entity path representation.
        :returns: tuple with entity type, entity id and project id
        """
        # TODO - replace with internal VMR conversion method

        # format example:
        # /projects/65/shots/862/tasks/568
        entity_type = "Task"
        project_id = int(path.split("/")[2])
        entity_id = int(path.split("/")[-1])
        return entity_type, entity_id, project_id

    def _populate_context_menu(self):
        """
        Populate the actions model with items suitable for the
        current context.

        It will check that shotgun itself hasn't changed (for example someone
        updating the software entity, which would in turn affect the list of actions).
        this happens periodically, at the most every CONFIG_CHECK_TIMEOUT_SECONDS seconds
        and if a change is detected, _on_configurations_changed is asynchronously invoked.

        Configurations for the current project are then requested to generate
        actions suitable for the current context.
        """
        logger.debug("Requesting commands for %s" % self._actions_model.currentEntityPath())

        (entity_type, entity_id, project_id) = self._path_to_entity(
            self._actions_model.currentEntityPath()
        )
        self._actions_model.clear()

        if project_id in self._cached_configs:
            logger.debug("Configurations cached in memory.")
            # we got the configs cached!
            # ping a check to check that shotgun pipeline configs are up to date
            cache_out_of_date = (time.time() - self._last_update_check) > self.CONFIG_CHECK_TIMEOUT_SECONDS
            if self._last_update_check is None or cache_out_of_date:
                # time to check with shotgun if there are updates
                logger.debug("Requesting a check to see if any changes have happened in shotgun.")
                self._last_update_check = time.time()
                # refresh - this may trigger a call to _on_configurations_changed
                self._command_handler.refresh()

            # request that menu items are emitted for the currently
            # cached configurations.
            self._request_commands(project_id, entity_type, entity_id)

        else:
            logger.debug("No configurations cached. Requesting load of configuration data for project %s" % project_id)
            # we don't have any configuration objects cached yet.
            # request it - _on_configurations_loaded will triggered when configurations are loaded
            self._command_handler.request_configurations(project_id)

    def _on_configurations_changed(self):
        """
        Indicates that the state of shotgun has changed
        and that we should discard any cached configurations and reload them.
        """
        logger.debug("Shotgun has changed. Discarding cached configurations.")
        # our cached configuration objects are no longer valid
        self._cached_configs = {}

        # load in new configurations for current project
        (entity_type, entity_id, project_id) = self._path_to_entity(
            self._actions_model.currentEntityPath()
        )
        # reload our configurations
        # _on_configurations_loaded will triggered when configurations are loaded
        logger.debug("Requesting new configurations for %s." % project_id)
        self._command_handler.request_configurations(project_id)

    def _on_configurations_loaded(self, project_id, configs):
        """
        Called when external configurations for the given project have been loaded.

        :param int project_id: Project id that configurations are assocaited with
        :param list configs: List of RemoteConfiguration instances belonging to the
            project_id.
        """
        logger.debug("Configs loaded for project %s" % project_id)

        # cache our configs
        self._cached_configs[project_id] = configs

        # wire up signals from our cached command objects
        for config in configs:
            config.commands_loaded.connect(self._on_commands_loaded)

        # and request commands to be loaded

        # make sure that the user hasn't switched to a different item
        # while things were loading
        (entity_type, entity_id, curr_project_id) = self._path_to_entity(
            self._actions_model.currentEntityPath()
        )
        if curr_project_id == project_id:
            self._request_commands(project_id, entity_type, entity_id)

    def _request_commands(self, project_id, entity_type, entity_id):
        """
        Requests commands for the given entity.

        This is an asynchronous operation which will call
        _on_commands_loaded() upon completion.

        :param int project_id: Shotgun project id
        :param str entity_type: Shotgun entity type
        :param int entity_id: Shotgun entity id
        """
        logger.debug(
            "Requesting commands for project %s, %s %s" % (project_id, entity_type, entity_id)
        )
        # set up a placeholder in the context model
        self._actions_model.clear()
        self._actions_model.appendAction("Loading actions...", "", "_LOADING")
        for config in self._cached_configs[project_id]:
            config.request_commands(
                self.ENGINE_NAME,
                entity_type,
                entity_id,
                link_entity_type=None  # TODO: <-- fix
            )

    def _on_commands_loaded(self, commands):
        """
        Called when commands have been loaded for a given configuration.

        Note that this may be called several times for a project, if the project
        has got several pipeline configurations (for example dev sandboxes).

        :param list commands: List of RemoteCommand instances.
        """
        # TODO - don't clear when we have multiple configs coming in.
        self._actions_model.clear()

        # this is *very* helpful :-)
        # TODO: remove at some point
        self._actions_model.appendAction(u"Reload Code \U0001F60E", "", "_RELOAD")

        for command in commands:
            # populate the actions model with actions.
            # serialize the remote command object so we can
            # unfold it at a later point without having to
            # retain any internal state
            self._actions_model.appendAction(
                command.display_name,
                command.tooltip,
                command.to_string()
            )

    def _execute_action(self, path, action_str):
        """
        Triggered from the engine when a user clicks an action

        :param str path: entity path representation.
        :param str action_str: serialized remotecommand payload.
        """
        if action_str == "_RELOAD":
            sgtk.platform.restart()

        else:
            # deserialize and execute
            external_config = self.frameworks["tk-framework-shotgunutils"].import_module("external_config")
            action = external_config.RemoteCommand.from_string(action_str)
            action.execute()

