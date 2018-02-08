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

class DesktopEngine2(Engine):
    """
    Shotgun Desktop v2 Engine
    """
    # QObject name for the C++ actions model
    ACTION_MODEL_OBJECT_NAME = "ToolkitActionModel"

    # the plugin id associated with this engine
    PLUGIN_ID = "basic.desktop2"

    # our engine name
    ENGINE_NAME = "tk-desktop2"

    # how often we check if shotgun configs have changed
    CONFIG_CHECK_TIMEOUT_SECONDS = 30

    def init_engine(self):
        """
        Main initialization entry point.
        """
        self._cached_configs = {}
        self._last_update_check = None

    def post_app_init(self):
        """
        Initialization that runs after all apps and the QT abstractions have been loaded.
        """
        from sgtk.platform.qt import QtCore, QtGui

        fw = self.frameworks["tk-framework-shotgunutils"]
        multi_context = fw.import_module("multi_context")
        task_manager = fw.import_module("task_manager")

        qt_parent = QtCore.QCoreApplication.instance()

        # create a background task manager
        self._task_manager = task_manager.BackgroundTaskManager(
            qt_parent,
            start_processing=True,
            max_threads=2
        )

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

            self._command_handler = multi_context.CommandHandler(
                self.PLUGIN_ID,
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
        All log messages from the toolkit logging namespace will be passed to this method.

        .. note:: To implement logging in your engine implementation, subclass
                  this method and display the record in a suitable way - typically
                  this means sending it to a built-in DCC console. In addition to this,
                  ensure that your engine implementation *does not* subclass
                  the (old) :meth:`Engine.log_debug`, :meth:`Engine.log_info` family
                  of logging methods.

                  For a consistent output, use the formatter that is associated with
                  the log handler that is passed in. A basic implementation of
                  this method could look like this::

                      # call out to handler to format message in a standard way
                      msg_str = handler.format(record)

                      # display message
                      print msg_str

        .. warning:: This method may be executing called from worker threads. In DCC
                     environments, where it is important that the console/logging output
                     always happens in the main thread, it is recommended that you
                     use the :meth:`async_execute_in_main_thread` to ensure that your
                     logging code is writing to the DCC console in the main thread.

        :param handler: Log handler that this message was dispatched from
        :type handler: :class:`~python.logging.LogHandler`
        :param record: Std python logging record
        :type record: :class:`~python.logging.LogRecord`
        """
        print "[tk-desktop2] %s" % handler.format(record)


    def destroy_engine(self):

        try:
            if self._command_handler:
                self._command_handler.shut_down()

            # shut down main threadpool
            self._task_manager.shut_down()

        except Exception, e:
            self.log_exception("Error running Engine teardown logic")



    def _path_to_entity(self, path):

        # /projects/65/shots/862/tasks/568
        logger.debug("path to entity: %s" % path)
        entity_type = "Task"
        project_id = int(path.split("/")[2])
        entity_id = int(path.split("/")[-1])
        return entity_type, entity_id, project_id

    def _populate_context_menu(self):
        """
        Request to populate a context menu in viewmaster
        """
        logger.debug("Viewmaster current entity path changed")

        from sgtk.platform.qt import QtCore, QtGui

        (entity_type, entity_id, project_id) = self._path_to_entity(
            self._actions_model.currentEntityPath()
        )
        self._actions_model.clear()
        self._actions_model.appendAction("Loading Actions...", "", "_LOADING")

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
            logger.debug("Requesting actions.")
            self._request_actions(self._cached_configs[project_id])

        else:
            logger.debug("No configurations cached. Requesting load of configuration data for project %s" % project_id)
            # we don't have any confinguration objects cached yet.
            # request it - _on_configurations_loaded will triggered when configurations are loaded
            self._actions_model.appendAction("Loading Actions...", "", "_LOADING")
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

        # and request actions to be loaded
        self._request_actions(configs)


    def _request_actions(self, configs):
        """
        Given a list of config objects, request commmands
        @param configs:
        @return:
        """
        (entity_type, entity_id, project_id) = self._path_to_entity(
            self._actions_model.currentEntityPath()
        )

        self._actions_model.clear()
        self._actions_model.appendAction("reload code", "", "_RELOAD")
        self._actions_model.appendAction("Loading Actions...", "", "_LOADING")
        for config in configs:
            config.request_commands(self.ENGINE_NAME, entity_type, entity_id, link_entity_type=None)

    def _on_commands_loaded(self, commands):
        logger.error("COMMANDSLODED")
        self._actions_model.appendAction("COMMAND", "", "_RELOAD")

    def _on_configurations_changed(self):
        """
        indicates that the state of shotgun has changed
        """
        logger.debug(">>>> SHOTGUN CNFIG CHANGE DETECTED!")
        # clear our cache
        self._cached_configs = {}

        # load in new configurations for current project
        (entity_type, entity_id, project_id) = self._path_to_entity(
            self._actions_model.currentEntityPath()
        )
        # reload our configurations - _on_configurations_loaded will triggered when configurations are loaded
        self._command_handler.request_configurations(project_id)

    def _execute_action(self, path, action_id):
        """
        Triggered from the engine when a user clicks an action
        @param path:
        @param action_id:
        @return:
        """
        logger.debug("Trigger command: %s %s" % (path, action_id))

        if action_id == "_RELOAD":
            sgtk.platform.restart()

        else:
            (entity_type, entity_id, project_id) = self._path_to_entity(path)
            self._command_handler.execute_command(
                "tk-desktop2",
                entity_type,
                entity_id,
                action_id
            )
