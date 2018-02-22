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
import threading
import os
import sys

logger = sgtk.LogManager.get_logger(__name__)


class DesktopEngine2(Engine):
    """
    Toolkit Engine for Shotgun Desktop v2
    """
    # QObject name for the C++ actions model
    ACTION_MODEL_OBJECT_NAME = "ToolkitActionModel"

    # how often we check if Shotgun configs have changed
    CONFIG_CHECK_TIMEOUT_SECONDS = 30

    # TODO - these constants should be passed down from the taap plugin
    # Engine instance name
    ENGINE_NAME = "tk-desktop2"
    # Configuration to load
    BASE_CONFIG = "sgtk:descriptor:app_store?name=tk-config-basic2"  # TODO - Rename to tk-config-basic
    # Toolkit plugin id
    PLUGIN_ID = "basic.desktop2"

    def init_engine(self):
        """
        Main initialization entry point.
        """
        # list of cached configuration objects, keyed by projet id
        self._cached_configs = {}
        # last time stamp we checked for new configs (unix time)
        self._last_update_check = 0
        # flag to indicate that the engine is running
        # TODO - will be replaced with better solution once we have QT support in VMR python.
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

        self._actions_model = None
        self._command_handler = None
        self._task_manager = None

        # todo - once we have QT support in VMR python this will go away
        qt_parent = QtCore.QCoreApplication.instance()
        if qt_parent:
            self._running_with_ui = True

            # create a background task manager
            self._task_manager = task_manager.BackgroundTaskManager(
                qt_parent,
                start_processing=True,
                max_threads=2
            )

            # set it up with the Shotgun globals
            shotgun_globals.register_bg_task_manager(self._task_manager)

            # todo - need to revisit this and set up a proper dark theme for VMR internally.
            self._initialize_dark_look_and_feel()

            try:
                logger.debug("Attempting to bind against underlying C++ actions model...")
                self._actions_model = self._get_action_model()
            except RuntimeError:
                logger.error(
                    "Could not retrieve internal ActionModel interface. "
                    "No actions will be displayed."
                )
            else:
                # install signals from actions model
                self._actions_model.currentEntityPathChanged.connect(self._populate_context_menu)
                self._actions_model.actionTriggered.connect(self._execute_action)

                # hook up remote configuration loader
                self._command_handler = external_config.RemoteConfigurationLoader(
                    self._get_python_interpreter_path(),
                    self.ENGINE_NAME,
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

        # TODO - this will change when we have more of an interface
        # in place on the C++ side as part of the toolkit baked bundling.
        if QtCore.QCoreApplication.instance() is None:
            raise RuntimeError("No QApplication found!")

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

            logger.debug("Engine shutdown complete.")

        except Exception as e:
            self.log_exception("Error running engine teardown logic")

    def _path_to_entity(self, path):
        """
        Converts a desktop-2 style path to Shotgun entities

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

    def _get_python_interpreter_path(self):
        """
        Returns the path to the desktop2 python interpreter

        :returns: Path to python
        """
        if sys.platform == "win32":
            return os.path.join(sys.prefix, "python.exe")
        else:
            return os.path.join(sys.prefix, "bin", "python")

    def _populate_context_menu(self):
        """
        Populate the actions model with items suitable for the
        current context.

        It will check that Shotgun itself hasn't changed (for example someone
        updating the software entity, which would in turn affect the list of actions).
        this happens periodically, at the most every CONFIG_CHECK_TIMEOUT_SECONDS seconds
        and if a change is detected, _on_configurations_changed is asynchronously invoked.

        Configurations for the current project are then requested to generate
        actions suitable for the current context.
        """
        logger.debug("Requesting commands for %s" % self._actions_model.currentEntityPath())

        # clear loading indicator
        self._actions_model.clear()

        (entity_type, entity_id, project_id) = self._path_to_entity(
            self._actions_model.currentEntityPath()
        )

        if project_id in self._cached_configs:
            logger.debug("Configurations cached in memory.")
            # we got the configs cached!
            # ping a check to check that Shotgun pipeline configs are up to date
            cache_out_of_date = (time.time() - self._last_update_check) > self.CONFIG_CHECK_TIMEOUT_SECONDS
            if cache_out_of_date:
                # time to check with Shotgun if there are updates
                logger.debug("Requesting a check to see if any changes have happened in Shotgun.")
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
            self._actions_model.appendAction("Loading Configurations...", "", "")
            self._command_handler.request_configurations(project_id)

    def _on_configurations_changed(self):
        """
        Indicates that the state of Shotgun has changed
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
        logger.debug("New configs loaded for project %s" % project_id)

        # clear any loading indication
        self._actions_model.clear()

        # cache our configs
        if configs and len(configs) > 0:
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

        else:
            logger.debug("No configuration associated with project id %s" % project_id)

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
        for config in self._cached_configs[project_id]:

            # indicate that we are loading data for this config
            self._add_config_loading_state(config)

            config.request_commands(
                entity_type,
                entity_id,
                link_entity_type=None  # TODO: <-- fix
            )

    def _on_commands_loaded(self, config, commands):
        """
        Called when commands have been loaded for a given configuration.

        Note that this may be called several times for a project, if the project
        has got several pipeline configurations (for example dev sandboxes).

        :param config: Associated RemoteConfiguration instance
        :param list commands: List of RemoteCommand instances.
        """
        # TODO - don't populate if the current context for the action model has changed.

        for command in commands:
            # populate the actions model with actions.
            # serialize the remote command object so we can
            # unfold it at a later point without having to
            # retain any internal state
            if config.is_primary:
                display_name = command.display_name
            else:
                display_name = "%s: %s" % (config.pipeline_configuration_name, command.display_name)

            self._actions_model.appendAction(
                display_name,
                command.tooltip,
                command.to_string()
            )

        # first remove any loading message associated with this batch
        self._remove_config_loading_state(config)
        self._actions_model.appendAction("Reload Code", "", "_RELOAD")

    def _execute_action(self, path, action_str):
        """
        Triggered from the engine when a user clicks an action

        :param str path: entity path representation.
        :param str action_str: serialized remotecommand payload.
        """
        if action_str == "_RELOAD":
            sgtk.platform.restart()

        elif action_str != "":
            # deserialize and execute
            external_config = self.frameworks["tk-framework-shotgunutils"].import_module("external_config")
            action = external_config.RemoteCommand.from_string(action_str)

            class Worker(threading.Thread):
                def run(self):
                    action.execute()

            worker = Worker()
            worker.start()

    def _add_config_loading_state(self, configuration):
        """
        Adds a loading message for the given config.
        """
        if configuration.is_primary:
            self._actions_model.appendAction("Loading...", "", "")
        else:
            self._actions_model.appendAction(
                "%s: Loading..." % configuration.pipeline_configuration_name, "", ""
            )

    def _remove_config_loading_state(self, configuration):
        """
        Removes a loading message for the given config.
        """
        if configuration.is_primary:
            label = "Loading..."
        else:
            label = "%s: Loading..." % configuration.pipeline_configuration_name

        root_item = self._actions_model.invisibleRootItem()
        for idx in range(self._actions_model.rowCount()):
            item = self._actions_model.item(idx)
            if item.text() == label:
                # remove it
                root_item.takeRow(idx)
                break
