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

    # QObject name for the C++ application engine object
    APPLICATION_ENGINE_OBJECT_NAME = "ApplicationEngine"

    def init_engine(self):
        """
        Main initialization entry point.
        """

    def post_app_init(self):

        # switch to dark styles.
        self._initialize_dark_look_and_feel()

        # test pop up the py console.
        # hack to get this to work due to weird error checks in py console...
        sgtk.platform.engine.g_current_engine = self
        self.commands["Shotgun Python Console..."]["callback"]()

    def _get_dialog_parent(self):
        """
        Return the QWidget parent for all dialogs created through
        show_dialog and show_modal.
        """
        # parenting logic is inside _create_dialog()
        return None

    def _create_dialog(self, title, bundle, widget, parent):
        """
        Create dialog and parent it to main window
        """

        from sgtk.platform.qt import QtCore, QtGui

        dialog = super(DesktopEngine2, self)._create_dialog(title, bundle, widget, parent)

        logger.debug("Created dialog %s" % dialog)

        application_engine = None
        app = QtCore.QCoreApplication.instance()
        for w in app.children():
            if w.objectName() == self.APPLICATION_ENGINE_OBJECT_NAME:
                application_engine = w
                break

        logger.debug("Found application engine %s" % application_engine)

        if application_engine:
            qml_main_window = application_engine.rootObjects()[0]
            dialog.winId()
            logger.debug("Parenting dialog %s to main window %s" % (dialog, qml_main_window))
            dialog.windowHandle().setTransientParent(qml_main_window)

        return dialog


