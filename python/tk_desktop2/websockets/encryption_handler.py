# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import os
import sgtk
import base64
from cryptography.fernet import Fernet  #  included as part of main application build

logger = sgtk.LogManager.get_logger(__name__)


class EncryptionHandler(object):
    """
    Handles the logic for encrypting the traffic to the current site.

    Upon construction, an API connection will be established and an exchange will be carried
    out whereby this class crafts a unique server id (available via the unique_server_id
    property). It will then send this to the shotgun site and in exchange get an encryption
    key. Once the shotgun site has provided this encryption key, this class can be used to
    encrypt and decrypt websockets traffic sent to the site.
    """

    def __init__(self):
        """
        :param str site_url: Shotgun site to create a site handler for.
        """
        self._bundle = sgtk.platform.current_bundle()

        # Compute a server id and retrieve the secret associated to it.
        # urandom is considered cryptographically secure as it calls the OS's CSRNG, so we can
        # use that to generate our own server id.
        self._unique_server_id = base64.urlsafe_b64encode(os.urandom(16))

        # get the secret from the shotgun site.
        # don't hold on to it but pass it to
        # the encryption library.
        ws_server_secret = self._retrieve_server_secret()

        # create encryption session
        self._fernet = Fernet(ws_server_secret)

    def __repr__(self):
        """
        String representation
        """
        return "<ws-site %s>" % self._bundle.sgtk.site_url

    @property
    def unique_server_id(self):
        """
        Unique id associated with this shotgun site.
        """
        return self._unique_server_id

    def encrypt(self, payload):
        """
        Encrypts the given payload

        :param str payload: String to encrypt.
        :returns: Encrypted string
        """
        return self._fernet.encrypt(payload)

    def decrypt(self, payload):
        """
        Decrypts the given payload

        :param str payload: String to decrypt.
        :returns: Decrypted string
        """
        b = bytes(payload)
        return self._fernet.decrypt(b)

    def _retrieve_server_secret(self):
        """
        Retrieves the server secret from Shotgun.

        :param shotgun: Shotugn API instance.
        :returns: Shotgun secret str.
        """
        logger.debug("Retrieving communication secret from Shotgun")
        # Ask for the secret for this server id.
        response = self._bundle.shotgun._call_rpc(
            "retrieve_ws_server_secret", {"ws_server_id": self._unique_server_id}
        )
        ws_server_secret = response["ws_server_secret"]

        # FIXME: Server doesn't seem to provide a properly padded string. The Javascript side
        # doesn't seem to complain however, so I'm not sure whose implementation is broken.
        if ws_server_secret[-1] != "=":
            ws_server_secret += "="

        return ws_server_secret
