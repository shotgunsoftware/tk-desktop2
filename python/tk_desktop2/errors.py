# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.


class ShotgunLocalHostCertNotSupportedError(RuntimeError):
    """
    Exception to indicate that the shotgunlocalhost certificate
    exchange feature isn't available.
    """


class PathParseError(RuntimeError):
    """
    Raised when a desktop2 style path cannot be parsed
    into shotgun-style dictionaries.
    """
