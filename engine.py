# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

from sgtk.platform import Engine
import sgtk
import os
import sys

logger = sgtk.LogManager.get_logger(__name__)


class DesktopEngine2(Engine):
    """
    Toolkit Engine for Shotgun Desktop v2
    """

    SHOTGUN_ENGINE_NAME = "tk-shotgun"

    def init_engine(self):
        """
        Main initialization entry point.
        """
        # handles in-ui menus
        self._actions_handler = None
        # handles background work
        self._task_manager = None
        # executes websockets tasks
        self._wss_runner = None
        # handles websockets server
        self._wss_handler = None

    def post_app_init(self):
        """
        Initialization that runs after all apps and the QT abstractions have been loaded.
        """
        self._initialize_dark_look_and_feel()

    def initialize_actions_integration(self, engine_instance_name, plugin_id, base_config):
        """
        Start up the engine's built in actions integration.

        This will attempt to bind against a ACTION_MODEL_OBJECT_NAME qt object
        which is assumed to be defined by C++ and establish a data exchange
        between this model and the engine.

        A Shotgun-utils external config instance is constructed to handle
        cross-context requests for actions and execution from the action model.

        :param str engine_instance_name: The instance name of the engine for
            which we should be retrieving commands.
        :param str plugin_id: The plugin id associated with the runtime environment.
        :param str base_config: Descriptor URI for the config to use by default when
            no custom pipeline configs have been defined in Shotgun.
        """
        from sgtk.platform.qt import QtCore, QtGui
        logger.debug("Begin initializing action integrations")
        logger.debug("Engine instance name: %s" % engine_instance_name)
        logger.debug("Plugin id: %s" % plugin_id)
        logger.debug("Base config: %s" % base_config)

        fw = self.frameworks["tk-framework-shotgunutils"]
        task_manager = fw.import_module("task_manager")
        shotgun_globals = fw.import_module("shotgun_globals")

        qt_parent = QtCore.QCoreApplication.instance()

        # create a background task manager
        self._task_manager = task_manager.BackgroundTaskManager(
            qt_parent,
            start_processing=True,
            max_threads=2
        )

        # set it up with the Shotgun globals
        shotgun_globals.register_bg_task_manager(self._task_manager)

        tk_desktop2 = self.import_module("tk_desktop2")

        # start up the action handler which handles menu interaction
        self._actions_handler = tk_desktop2.ActionHandler(
            engine_instance_name,
            plugin_id,
            base_config,
            self._task_manager
        )

        # initialize the runner which executes websocket commands
        self._wss_runner = tk_desktop2.RequestRunner(
            self.SHOTGUN_ENGINE_NAME,
            plugin_id,
            base_config,
            self._task_manager
        )

        # start up websockets server
        self._wss_handler = tk_desktop2.WebsocketsServer(
            self._wss_runner
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
        print "[sgtk] %s" % handler.format(record)

    def destroy_engine(self):
        """
        Engine shutdown.
        """
        logger.debug("Begin shutting down engine.")

        fw = self.frameworks["tk-framework-shotgunutils"]
        shotgun_globals = fw.import_module("shotgun_globals")

        try:
            if self._actions_handler:
                self._actions_handler.destroy()

            if self._wss_handler:
                self._wss_handler.destroy()

            # shut down main thread pool
            if self._task_manager:
                logger.debug("Stopping worker threads.")
                shotgun_globals.unregister_bg_task_manager(self._task_manager)
                self._task_manager.shut_down()

            logger.debug("Engine shutdown complete.")

        except Exception as e:
            self.log_exception("Error running engine teardown logic")

    @property
    def python_interpreter_path(self):
        """
        The path to the desktop2 python interpreter
        """
        if sys.platform == "win32":
            return os.path.abspath(os.path.join(sys.prefix, "python.exe"))
        else:
            return os.path.abspath(os.path.join(sys.prefix, "bin", "python"))
