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


class DesktopEngine2(Engine):
    """
    Shotgun Desktop v2 Engine
    """

    def __init__(self, *args, **kwargs):
        super(DesktopEngine2, self).__init__(*args, **kwargs)
	self.host_name = ""
	self.host_version = "0.0.0"	


    @property 
    def host_info(self):
        """
        Returns information about the application hosting this engine.

        This should be re-implemented in deriving classes to handle the logic
        specific to the application the engine is designed for.

        A dictionary with at least a "name" and a "version" key should be returned
        by derived implementations, with respectively the host application name
        and its release string as values, e.g. { "name": "Maya", "version": "2017.3"}.

        :returns: A {"name": "unknown", "version" : "unknown"} dictionary.
        """
        return {
            "name": self.host_name,
            "version": self.host_version
        }

    @host_info.setter
    def host_info(self, host_info):
        name, version = host_info
        self.host_name = name
        self.host_version = version
