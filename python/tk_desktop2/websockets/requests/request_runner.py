# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import sys
import sgtk
import json
import datetime

logger = sgtk.LogManager.get_logger(__name__)



class RequestRunner(object):
    """
    Exexcutes websockets Request objects
    """

    def __init__(self, engine_instance_name, plugin_id, base_config, task_manager):
        """
        Start up the engine's built in request runner

        :param str engine_instance_name: The instance name of the engine for
            which we should be retrieving commands.
        :param str plugin_id: The plugin id associated with the runtime environment.
        :param str base_config: Descriptor URI for the config to use by default when
            no custom pipeline configs have been defined in Shotgun.
        """
        logger.debug("Begin initializing RequestRunner")
        logger.debug("Engine instance name: %s" % engine_instance_name)
        logger.debug("Plugin id: %s" % plugin_id)
        logger.debug("Base config: %s" % base_config)



    def execute(self, request):
        """
        Executes a websockets request
        @param request:
        @return:
        """