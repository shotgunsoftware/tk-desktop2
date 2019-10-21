# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

# todo - read this out of the SG prefs
WEBSOCKETS_PORT_NUMBER = 9000

# version of the protocol that this implementation supports
WEBSOCKETS_PROTOCOL_VERSION = 2

# the shotgun Create preferences area
SHOTGUN_CREATE_PREFS_NAME = "view_master_settings"
# the key to look for to control the websockets port
SHOTGUN_CREATE_PREFS_WEBSOCKETS_PORT_KEY = "websockets_port"

# connection error codes
CONNECTION_REFUSED_USER_MISMATCH = "CONNECTION_REFUSED_USER_MISMATCH"
CONNECTION_REFUSED_SITE_MISMATCH = "CONNECTION_REFUSED_SITE_MISMATCH"

# shotgun version which is designed to respond to
# error states correctly
SHOTGUN_VERSION_SUPPORTING_ERROR_STATES = (8, 4, 0)
