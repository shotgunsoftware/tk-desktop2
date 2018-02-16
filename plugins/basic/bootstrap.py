# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import sys
import os
import imp
import uuid
import sgtk

def bootstrap_plugin():
    """
    Bootstrap this plugin.
    """
    # Initialize logging to disk
    sgtk.LogManager().initialize_base_file_handler("tk-desktop2")
    sgtk.LogManager().global_debug = True #manifest.debug_logging

    # log to stderr
    sgtk.LogManager().initialize_custom_handler()

    logger = sgtk.LogManager.get_logger("bootstrap")
    logger.info("Bootstrapping tk-desktop2...")

    # Figure out our location
    plugin_root_dir = os.path.abspath(os.path.dirname(__file__))
    plugin_python_path = os.path.join(plugin_root_dir, "python")

    # As a baked plugin we do have manifest.py we can use to bootstrap.
    # Import it.
    try:
        mfile, pathname, description = imp.find_module(
            "sgtk_plugin_basic_desktop2", [plugin_python_path]
        )
    except ImportError:
        logger.error(
            "Unable to find 'sgtk_plugin_basic_desktop2', was the plugin baked?"
        )
        raise

    # We use a uuid to make sure the code imported here will not conflict with
    # other plugins
    module_uid = "bootstrap%s" % uuid.uuid4().hex
    try:
        sgtk_plugin_basic_desktop2 = imp.load_module(
            "%s.%s" % (module_uid, "sgtk_plugin_basic_desktop2"),
            mfile,
            pathname,
            description
        )
    finally:
        if mfile:
            mfile.close()

    # This module is built with the plugin and contains the manifest.py.
    manifest = sgtk_plugin_basic_desktop2.manifest

    # start up toolkit via the manager - we should be authenticated already.
    manager = sgtk.bootstrap.ToolkitManager()
    manifest.initialize_manager(manager, plugin_root_dir)

    # start up in site mode.
    engine = manager.bootstrap_engine("tk-desktop2", entity=None)
    logger.info("tk-desktop2 is ready.")

if __name__ == "__main__":
    bootstrap_plugin()
