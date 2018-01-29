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

logger = sgtk.LogManager.get_logger(__name__)


class DesktopEngine2(Engine):
    """
    Shotgun Desktop v2 Engine
    """
    # QObject name for the C++ actions model
    ACTION_MODEL_OBJECT_NAME = "ToolkitActionModel"

    def init_engine(self):
        """
        Main initialization entry point.
        """

    def post_app_init(self):
        """
        Initialization that runs after all apps and the QT abstractions have been loaded.
        """
        from sgtk.platform.qt import QtCore, QtGui

        logger.debug("Attempting to bind against underlying C++ actions model...")
        self._actions_model = None
        for q_object in QtCore.QCoreApplication.instance().children():
            if q_object.objectName() == self.ACTION_MODEL_OBJECT_NAME:
                self._actions_model = q_object
                logger.debug("Found actions model %s" % self._actions_model)
                break

        if self._actions_model:
            # install signals
            self._actions_model.currentContextChanged.connect(self._populate_context_menu)
            self._actions_model.actionTriggered.connect(self._execute_action)
        else:
            logger.error(
                "Could not bind to actions model '%s'. "
                "No actions will be rendered" % self.ACTION_MODEL_OBJECT_NAME
            )

    def _populate_context_menu(self):
        from sgtk.platform.qt import QtCore, QtGui
        print "Context menu populate!"
        self._actions_model.clear()

        for (command_name, command_data) in self.commands.iteritems():
            print "parsing %s %s" % (command_name, command_data)
            display_name = command_data["properties"].get("title") or command_name
            tooltip = command_data["properties"].get("description") or ""
            self._actions_model.appendAction(display_name, tooltip, command_name)

    def _execute_action(self, path, action_id):
        print "Trigger command: %s %s" % (path, action_id)

        self.commands[action_id]["callback"]()



