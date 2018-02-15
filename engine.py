# Copyright (c) 2017 Shotgun Software Inc.
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

global SGTK_PLUGIN_CONSTANTS

class DesktopEngine2(Engine):
    """
    Shotgun Desktop v2 Engine
    """
    # QObject name for the C++ actions model
    ACTION_MODEL_OBJECT_NAME = "ToolkitActionModel"

    # todo - these should really be passed down from the plugin
    # our engine name
    ENGINE_NAME = "tk-desktop2"
    # configuration to load -- TODO - rename to tk-config-basic later on
    BASE_CONFIG = "sgtk:descriptor:app_store?name=tk-config-basic2"
    BASE_CONFIG = "sgtk:descriptor:dev?path=/Users/manne/Documents/work_dev/toolkit/tk-config-basic2"
    # toolkit plugin id
    PLUGIN_ID = "basic.desktop2"

    # how often we check if shotgun configs have changed
    CONFIG_CHECK_TIMEOUT_SECONDS = 30

    def init_engine(self):
        """
        Main initialization entry point.
        """
        self._cached_configs = {}
        self._last_update_check = None
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

            logger.debug("Attempting to bind against underlying C++ actions model...")
            self._actions_model = None
            self._command_handler = None

            for q_object in QtCore.QCoreApplication.instance().children():
                if q_object.objectName() == self.ACTION_MODEL_OBJECT_NAME:
                    self._actions_model = q_object
                    logger.debug("Found actions model %s" % self._actions_model)
                    break

            if self._actions_model:
                # install signals
                self._actions_model.currentEntityPathChanged.connect(self._populate_context_menu)
                self._actions_model.actionTriggered.connect(self._execute_action)

                self._command_handler = external_config.RemoteConfigurationLoader(
                    self.PLUGIN_ID,
                    self.BASE_CONFIG,
                    self._task_manager,
                    qt_parent
                )
                self._command_handler.configurations_loaded.connect(self._on_configurations_loaded)
                self._command_handler.configurations_changed.connect(self._on_configurations_changed)

            else:
                logger.error(
                    "Could not bind to actions model '%s'. "
                    "No actions will be rendered" % self.ACTION_MODEL_OBJECT_NAME
                )


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
        Engine shutdown
        """
        fw = self.frameworks["tk-framework-shotgunutils"]
        shotgun_globals = fw.import_module("shotgun_globals")

        try:
            if self._actions_model:
                # make sure that we release signals from the C++ object
                self._actions_model.currentEntityPathChanged.disconnect(self._populate_context_menu)
                self._actions_model.actionTriggered.disconnect(self._execute_action)
                self._actions_model = None

            if self._command_handler:
                self._command_handler.shut_down()

            # shut down main thread pool
            if self._task_manager:
                shotgun_globals.unregister_bg_task_manager(self._task_manager)
                self._task_manager.shut_down()

        except Exception, e:
            self.log_exception("Error running Engine teardown logic")

    def _path_to_entity(self, path):
        """
        Converts a VMR path to shotgun entities
        """
        # TODO - replace with internal VMR conversion method
        # /projects/65/shots/862/tasks/568
        entity_type = "Task"
        project_id = int(path.split("/")[2])
        entity_id = int(path.split("/")[-1])
        return entity_type, entity_id, project_id

    def _populate_context_menu(self):
        """
        Request to populate a context menu in viewmaster
        """
        logger.debug("VMR current entity path changed to %s" % self._actions_model.currentEntityPath())

        from sgtk.platform.qt import QtCore, QtGui

        (entity_type, entity_id, project_id) = self._path_to_entity(
            self._actions_model.currentEntityPath()
        )
        self._actions_model.clear()

        if project_id in self._cached_configs:
            logger.debug("Configurations cached in memory.")
            # we got the configs cached!
            # ping a check to check that shotgun pipeline configs are up to date
            if self._last_update_check is None or time.time() - self._last_update_check > self.CONFIG_CHECK_TIMEOUT_SECONDS:
                # time to check with shotgun if there are updates
                logger.debug("Requesting a check to see if any changes have happened in shotgun.")
                self._last_update_check = time.time()
                # refresh - this may trigger a call to _on_configurations_changed
                self._command_handler.refresh()

            # populate items
            self._request_commands(project_id, entity_type, entity_id)

        else:
            logger.debug("No configurations cached. Requesting load of configuration data for project %s" % project_id)
            # we don't have any confinguration objects cached yet.
            # request it - _on_configurations_loaded will triggered when configurations are loaded
            self._command_handler.request_configurations(project_id)

    def _on_configurations_loaded(self, project_id, configs):
        """
        indicates that the configurations for a given project has changed and needs
        recomputing.
        @param project_id:
        @return:
        """
        logger.debug("Configs loaded for project %s" % project_id)

        # cache our configs
        self._cached_configs[project_id] = configs

        # wire up signals from our cached command objects
        for config in configs:
            config.commands_loaded.connect(self._on_commands_loaded)

        # and request commands to be loaded
        (entity_type, entity_id, curr_project_id) = self._path_to_entity(
            self._actions_model.currentEntityPath()
        )

        # make sure that the user hasn't switched to a different item
        # while things were loading
        if curr_project_id == project_id:
            self._request_commands(project_id, entity_type, entity_id)

    def _request_commands(self, project_id, entity_type, entity_id):

        logger.debug("Requesting commands.")
        self._actions_model.clear()
        self._actions_model.appendAction("Loading actions...", "", "_LOADING")
        for config in self._cached_configs[project_id]:
            config.request_commands(
                self.ENGINE_NAME,
                entity_type,
                entity_id,
                link_entity_type=None  #todo: <-- fix
            )

    def _on_commands_loaded(self, commands):
        """
        Commands loaded for a configuration
        """
        # todo - don't clear when we have multiple configs coming in.
        self._actions_model.clear()
        self._actions_model.appendAction(u"Reload Code \U0001F60E", "", "_RELOAD")
        for command in commands:
            self._actions_model.appendAction(
                command.display_name,
                command.tooltip,
                command.to_string()
            )

    def _on_configurations_changed(self):
        """
        indicates that the state of shotgun has changed
        """
        # our cached configuration objects are no longer valid
        self._cached_configs = {}

        # load in new configurations for current project
        (entity_type, entity_id, project_id) = self._path_to_entity(
            self._actions_model.currentEntityPath()
        )
        # reload our configurations - _on_configurations_loaded will triggered when configurations are loaded
        self._command_handler.request_configurations(project_id)

    def _execute_action(self, path, action_str):
        """
        Triggered from the engine when a user clicks an action
        @param path:
        @param action_id:
        @return:
        """
        logger.debug("Trigger command: %s" % path)

        if action_str == "_RELOAD":
            sgtk.platform.restart()

        else:
            external_config = self.frameworks["tk-framework-shotgunutils"].import_module("external_config")
            action = external_config.RemoteCommand.from_string(action_str)
            action.execute()

