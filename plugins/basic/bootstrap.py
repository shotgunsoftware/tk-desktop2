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
import sgtk

ENGINE_NAME = "tk-desktop2"

def bootstrap_plugin(global_debug=True):
    """
    Bootstrap this plugin.

    :param bool global_debug: Whether or not Sgtk global debug should be activated.
    """
    # Initialize logging to disk
    sgtk.LogManager().initialize_base_file_handler(ENGINE_NAME)
    sgtk.LogManager().global_debug = global_debug

    # Log to stderr
    sgtk.LogManager().initialize_custom_handler()

    logger = sgtk.LogManager.get_logger("bootstrap")
    logger.debug("Bootstrapping %s..." % ENGINE_NAME)

    # Figure out our location
    plugin_root_dir = os.path.abspath(os.path.dirname(__file__))
    plugin_python_path = os.path.join(plugin_root_dir, "python")

    # As a baked plugin we do have manifest.py we can use to bootstrap.

    # Instead of adding an extra path in the PYTHONPATH to be able to load the
    # manifest module and clean up the PYTHONPATH up after the import, we use
    # `imp` utilities to load the manifest module.
    try:
        mfile, pathname, description = imp.find_module(
            "sgtk_plugin_basic_desktop2", [plugin_python_path]
        )
    except ImportError:
        logger.error(
            "Unable to find 'sgtk_plugin_basic_desktop2', was the plugin baked?"
        )
        raise

    try:
        sgtk_plugin_basic_desktop2 = imp.load_module(
            "sgtk_plugin_basic_desktop2",
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
    engine = manager.bootstrap_engine(ENGINE_NAME, entity=None)
    logger.debug("%s is ready." % engine.name)

if __name__ == "__main__":
    bootstrap_plugin()
