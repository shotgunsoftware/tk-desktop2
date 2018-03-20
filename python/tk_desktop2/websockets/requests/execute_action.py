# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import sgtk
import json
import pprint
import datetime
from .base import WebsocketsRequest

logger = sgtk.LogManager.get_logger(__name__)


class ExecuteActionWebsocketsRequest(WebsocketsRequest):

    def __init__(self, connection, id, parameters):
        super(ExecuteActionWebsocketsRequest, self).__init__(connection, id)

    @property
    def project_id(self):
        """
        Project id associated with this request or None for a site wide request
        """
        return None

    @property
    def entity_type(self):
        """
        Entity type with this request or None for a site wide request
        """
        return None

    @property
    def entity_id(self):
        """
        Entity id with this request or None for a site wide request
        """
        return None

    def execute(self, configurations):
        """
        Executes the request. Passes a fully loaded external
        configuration state to aid execution, laid out in the following
        structure:

        [
            {
                "configuration": <ExternalConfiguration>,
                "commands": [<ExternalCommand>, ...],
                "error": None
            },
            {
                "configuration": <ExternalConfiguration>,
                "commands": None,
                "error": "Something went wrong"
            },
        ]

        :param list configurations: See above for details.
        """
        raise NotImplementedError("WebsocketsRequest.execute not implemented by deriving class.")
