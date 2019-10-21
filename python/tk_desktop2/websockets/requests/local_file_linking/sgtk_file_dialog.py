# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import os
import sys
import traceback

import sgtk
from sgtk.util import ShotgunPath
from sgtk.platform.qt import QtCore, QtGui

logger = sgtk.LogManager.get_logger(__name__)


class SgtkFileDialog(QtGui.QFileDialog):
    """
    This is a QT file dialog that allows extended selection.
    Note that it doesn't quite succeed at this in every os as
    some can't do both file and folder extended selection.
    """

    # class level cache of queried local storages as defined in SG. These will
    # be queried the first time they're needed, then reused after that.
    LOCAL_STORAGES = None

    def __init__(self, multi=False, *args, **kwargs):
        """
        Initialize file dialog.

        :param multi: Allow extended selection
        """
        super(SgtkFileDialog, self).__init__(*args, **kwargs)

        # set the browsing mode (single or multi files)
        if multi:
            self.setFileMode(QtGui.QFileDialog.ExistingFiles)
        else:
            self.setFileMode(QtGui.QFileDialog.ExistingFile)

        # display some additional, useful shortcuts in the sidebar. Not
        # essential, so wrapped in a try
        try:
            self._update_sidebar_urls()
        except Exception as e:
            logger.warning(
                "Unable to add sidebar URLs to file dialog."
                "Full error: %s" % (traceback.format_exc(),)
            )

        # Make the combobox editable so we can specify a path through it. Not
        # essential, so wrapped in a try
        try:
            self._make_combo_editable()
        except Exception as e:
            logger.warning(
                "Unable to make file dialog combo box editable."
                "Full error: %s" % (traceback.format_exc(),)
            )

    def exec_(self):
        """
        Shows the window modally and in the foreground.

        :returns: The return code specified by the call to quit().
        """
        self.show()
        self.raise_()
        self.activateWindow()

        # the trick of activating + raising does not seem to be enough for
        # modal dialogs. So force put them on top as well.
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint | self.windowFlags())
        return QtGui.QDialog.exec_(self)

    def accept(self, *args, **kwargs):
        """
        Override method for accept button.

        Allows to emit an event with the list of selected files.
        """
        files = self.selectedFiles()
        if not files:
            return

        self.fileSelected.emit(files)
        QtGui.QDialog.accept(self, *args, **kwargs)

    def _make_combo_editable(self):
        """Makes the "Look in" combo box editable for usability."""

        # try to find the combo box
        combo = self.findChild(QtGui.QComboBox, "lookInCombo")
        combo.setEditable(True)

        # Search for the line edit widget, it has no name so scan for it.
        line_edits = filter(lambda c: isinstance(c, QtGui.QLineEdit), combo.children())

        if len(line_edits) != 1:
            logger.warning(
                "Couldn't locate line edit for 'look in' combo box while "
                "attempting to make it editable."
            )
            return

        # If there's only one, assume that's the path editor. When the user
        # presses return, we'll move to the directory indicated by its text.
        path_editor = line_edits[0]
        path_editor.returnPressed.connect(
            lambda pe=path_editor: self.setDirectory(pe.text())
        )

    def _update_sidebar_urls(self):
        """Updates the sidebar URLs in the file dialog for convenience.

        On OSX, adds "/Volumes". Also adds the curernt os path for all SG local
        storages defined in SG.
        """

        # This is required to modify the sidebar urls
        self.setOption(QtGui.QFileDialog.DontUseNativeDialog)

        # get the current sidebar urls
        sidebar_urls = self.sidebarUrls()

        # also add paths to the local storages for the current OS since you're
        # only allowed to link files under these locations.
        engine = sgtk.platform.current_engine()

        # Commenting out the local storages in the sidebar for now. While there
        # is value here, there are some annoying things that make it not worth
        # including yet. Namely, there's no control over how the urls are
        # displayed. This means that two storages with the same folder names
        # will show up identically in the sidebar. Also, modifying the sidebar
        # here appears to be persistent so that other QFileDialogs opened,
        # say in the publisher, will retain the storage links.
        """
        # add local storages to the sidebar
        path_field = ShotgunPath.get_shotgun_storage_key()
        if path_field:

            # check against None here since there may not be storages defined
            if self.LOCAL_STORAGES is None:
                self.LOCAL_STORAGES = engine.shotgun.find(
                    "LocalStorage",
                    [],
                    [path_field]
                )

            # no point in sorting here. file dialog seems to have it's own
            # sorting algorithm that overrides the order in which urls are added
            # while also defying all common sense. /shrug
            for storage in self.LOCAL_STORAGES:

                # retrieve the storage path for this OS
                storage_path = storage.get(path_field)

                # if it exists, and isn't already in the sidebar URLs, append
                # it to the list of urls
                if storage_path and os.path.exists(storage_path):
                    url = QtCore.QUrl.fromLocalFile(storage_path)
                    if url not in sidebar_urls:
                        sidebar_urls.append(url)
        """

        # add Volumes to the sidebar on OSX
        if sys.platform == "darwin":
            volumes_url = QtCore.QUrl.fromLocalFile("/Volumes")
            if volumes_url not in sidebar_urls:
                sidebar_urls.append(volumes_url)

        self.setSidebarUrls(sidebar_urls)
