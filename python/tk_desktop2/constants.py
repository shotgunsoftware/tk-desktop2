# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

# How often we should reach out to Shotgun and check if the
# pipeline configurations, software entities and other
# shotgun global state has changed.
CONFIG_CHECK_TIMEOUT_SECONDS = 10

# The engine to use as a fallback if a tk-desktop2 engine
# definition isn't found in the environment we're getting
# actions from. This covers backwards compatibility with
# older configs that might not be setup with tk-desktop2.
FALLBACK_ENGINE = "tk-shotgun"
