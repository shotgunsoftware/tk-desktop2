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

# the shotgun preference to read to determine port
SHOTGUN_WSS_PORT_PREFERENCE_NAME = "shotgun_create_server_port"

# connection error codes
CONNECTION_REFUSED_USER_MISMATCH = "CONNECTION_REFUSED_USER_MISMATCH"
CONNECTION_REFUSED_SITE_MISMATCH = "CONNECTION_REFUSED_SITE_MISMATCH"
CONNECTION_REFUSED_NOT_AUTHENTICATED = "CONNECTION_REFUSED_SERVER_NOT_AUTHENTICATED"
