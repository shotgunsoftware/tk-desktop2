# Copyright (c) 2016 Shotgun Software Inc.
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
import sgtk

def bootstrap_plugin(plugin_root_dir):
    # figure out our location
    plugin_python_path = os.path.join(plugin_root_dir, "python")
    sys.path.insert(0, plugin_python_path)

    # This module is built with the plugin and contains the manifest.py.
    from sgtk_plugin_basic_desktop2 import manifest

    # initialize logging to disk
    sgtk.LogManager().initialize_base_file_handler("tk-desktop2")
    sgtk.LogManager().global_debug = True #manifest.debug_logging

    # log to stderr
    sgtk.LogManager().initialize_custom_handler()

    logger = sgtk.LogManager.get_logger(__name__)
    logger.info("Hello from viewmaster bootstrapper!")

    # start up toolkit via the manager - we should be authenticated already.
    manager = sgtk.bootstrap.ToolkitManager()
    manifest.initialize_manager(manager, plugin_root_dir)

    # start up in site mode.
    engine = manager.bootstrap_engine("tk-desktop2", entity=None)


