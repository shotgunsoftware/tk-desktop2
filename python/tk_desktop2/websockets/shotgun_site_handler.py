# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import os
import sgtk
import base64
from cryptography.fernet import Fernet #  included as part of main application build

logger = sgtk.LogManager.get_logger(__name__)


class ShotgunSiteHandler(object):
    """
    The shotgun site that we are connected to
    """

    def __init__(self, site_url):
        """
        """
        self._bundle = sgtk.platform.current_bundle()

        self._site_url = site_url

        # Compute a server id and retrieve the secret associated to it.
        # urandom is considered cryptographically secure as it calls the OS's CSRNG, so we can
        # use that to generate our own server id.
        self._unique_server_id = base64.urlsafe_b64encode(os.urandom(16))

        dm = sgtk.authentication.DefaultsManager(fixed_host=site_url)
        sg_auth = sgtk.authentication.ShotgunAuthenticator(dm)
        user = sg_auth.get_user()
        # todo: handle authenticationcancelled

        self._ws_server_secret = self._retrieve_server_secret(
            user.create_sg_connection()
        )

        # create encryption session
        self._fernet = Fernet(self._ws_server_secret)

    def __repr__(self):
        return "<Wss-site %s>" % self._site_url

    @property
    def unique_server_id(self):
        return self._unique_server_id

    def encrypt(self, payload):
        """
        Encrypts the given payload
        """
        return self._fernet.encrypt(payload)

    def decrypt(self, payload):
        """
        Decrypts the given payload
        """
        b = bytes(payload)
        return self._fernet.decrypt(b)

    def _retrieve_server_secret(self, shotgun):
        """
        Retrieves the server secret from Shotgun.
        """
        logger.debug("Retrieving communication secret from Shotgun")
        # Ask for the secret for this server id.
        response = shotgun._call_rpc(
            "retrieve_ws_server_secret", {"ws_server_id": self._unique_server_id}
        )
        ws_server_secret = response["ws_server_secret"]
        # FIXME: Server doesn't seem to provide a properly padded string. The Javascript side
        # doesn't seem to complain however, so I'm not sure whose implementation is broken.
        if ws_server_secret[-1] != "=":
            ws_server_secret += "="

        return ws_server_secret
