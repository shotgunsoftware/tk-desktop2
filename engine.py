# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

from sgtk.platform import Engine
import traceback
import logging
import sgtk
import os
import sys

logger = sgtk.LogManager.get_logger(__name__)


class DesktopEngine2(Engine):
    """
    Toolkit Engine for Shotgun Desktop v2
    """

    SHOTGUN_ENGINE_NAME = "tk-shotgun"

    def pre_app_init(self):
        """
        Main initialization entry point.
        """
        # handles in-ui menus
        self._actions_handler = None
        # handles background work
        self._task_manager = None
        # executes websockets tasks
        self._ws_runner = None
        # handles websockets server
        self._ws_handler = None
        # exposes methods of communicating with the host application
        self._toolkit_manager = None

        # Setup the styling to be inherited by child apps.
        self._initialize_dark_look_and_feel()

    def post_app_init(self):
        """
        Initialization that runs after all apps and the QT abstractions have been loaded.
        """
        from sgtk import LogManager

        LogManager().global_debug = True

    @property
    def toolkit_manager(self):
        """
        A handle to the manager object provided by the host application that exposes
        some necessary functionality. Methods exposed via this object effectively
        act as the "API" for Shotgun create.

        .. note:: This property is only set when the tk-desktop2 process is running inside
                  the Shotgun Create application. The tk-desktop2 engine can also run
                  in a separate external process (for example when you launch an app
                  such as the publisher from Shotgun Create).
        """
        try:
            from sgtk.platform.qt import QtCore

            return QtCore.QCoreApplication.instance().findChild(
                QtCore.QObject, "sgtk-manager"
            )
        except Exception:
            return None

    def initialize_integrations(self, plugin_id, base_config):
        """
        Start up the engine's built in actions integration
        and launch the websockets (shotgun integrations) server.

        This will attempt to bind against a ACTION_MODEL_OBJECT_NAME qt object
        which is assumed to be defined by C++ and establish a data exchange
        between this model and the engine.

        A Shotgun-utils external config instance is constructed to handle
        cross-context requests for actions and execution from the action model.

        :param str plugin_id: The plugin id associated with the runtime environment.
        :param str base_config: Descriptor URI for the config to use by default when
            no custom pipeline configs have been defined in Shotgun.
        """
        try:
            self._initialize_integrations(plugin_id, base_config)
        except Exception:

            # NOTE: markdown formatting in sgds toast doesn't currently
            # work, so just doing normal text instead of a preformatted
            # segment for the call stack.

            # error message - gets shown as a toast.
            message = "Failed to initialize integrations.\n\n"
            message += "%s - %s\n\n" % (sys.exc_type.__name__, sys.exc_value[0])
            message += "For more details, see the error logs."
            logger.error(message)

            # log full stack as a warning
            message += traceback.format_exc()
            logger.warning(message)

    def _initialize_integrations(self, plugin_id, base_config):
        """
        Implementation of :meth:`initialize_integrations`.

        :param str plugin_id: The plugin id associated with the runtime environment.
        :param str base_config: Descriptor URI for the config to use by default when
            no custom pipeline configs have been defined in Shotgun.
        """
        from sgtk.platform.qt import QtCore, QtGui

        logger.debug("Begin initializing action integrations")
        logger.debug("Engine instance name: %s" % self.name)
        logger.debug("Plugin id: %s" % plugin_id)
        logger.debug("Base config: %s" % base_config)

        fw = self.frameworks["tk-framework-shotgunutils"]
        task_manager = fw.import_module("task_manager")
        shotgun_globals = fw.import_module("shotgun_globals")

        qt_parent = QtCore.QCoreApplication.instance()

        # create a background task manager
        self._task_manager = task_manager.BackgroundTaskManager(
            qt_parent, start_processing=True, max_threads=1
        )

        # set it up with the Shotgun globals
        shotgun_globals.register_bg_task_manager(self._task_manager)

        tk_desktop2 = self.import_module("tk_desktop2")

        # start up the action handler which handles menu interaction
        self._actions_handler = tk_desktop2.ActionHandler(
            plugin_id, base_config, self._task_manager
        )

        # initialize the runner which executes websocket commands
        self._ws_runner = tk_desktop2.RequestRunner(
            self.SHOTGUN_ENGINE_NAME, plugin_id, base_config, self._task_manager
        )

        # start up websockets server
        self._ws_handler = tk_desktop2.WebsocketsServer(self._ws_runner)

    def _emit_log_message(self, handler, record):
        """
        Called by the engine whenever a new log message is available.

        :param handler: Log handler that this message was dispatched from
        :type handler: :class:`~python.logging.LogHandler`
        :param record: Std python logging record
        :type record: :class:`~python.logging.LogRecord`
        """

        if self.toolkit_manager:
            # Redirect all log messages to the app console
            if hasattr(self.toolkit_manager, "logMessage"):
                if record.levelno >= logging.ERROR:
                    log_level = "error"
                elif record.levelno >= logging.WARNING:
                    log_level = "warn"
                elif record.levelno >= logging.INFO:
                    log_level = "info"
                else:  # record.levelno < logging.INFO
                    log_level = "debug"

                self.toolkit_manager.logMessage(log_level, record.message)

            # Log a toast when the level is higher than Warning
            if (
                hasattr(self.toolkit_manager, "emitToast")
                and record.levelno > logging.WARNING
            ):
                # note: there seems to be an odd bug where colons truncate the message
                # as a workaround, remove all colons
                cleaned_up_message = record.message.replace(":", ".")
                # note: toasts support markdown
                message = "**Shotgun Integration Error**\n\n%s" % (cleaned_up_message,)

                self.toolkit_manager.emitToast(
                    message, "error", True  # don't automatically close.
                )

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
                self._actions_handler = None

            if self._ws_handler:
                self._ws_handler.destroy()
            self._ws_handler = None

            # shut down main thread pool
            if self._task_manager:
                logger.debug("Stopping worker threads.")
                shotgun_globals.unregister_bg_task_manager(self._task_manager)
                self._task_manager.shut_down()

            logger.debug("Engine shutdown complete.")

        except Exception as e:
            self.logger.exception("Error running engine teardown logic")

    @property
    def python_interpreter_path(self):
        """
        The path to the desktop2 python interpreter
        """
        if sys.platform == "win32":
            # use pythonw in order to prevent a shell window from
            # popping up. May need to refine this solution in the future.
            return os.path.abspath(os.path.join(sys.prefix, "pythonw.exe"))
        else:
            return os.path.abspath(os.path.join(sys.prefix, "bin", "python"))
