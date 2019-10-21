# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import os
import sgtk

from .errors import ShotgunLocalHostCertNotSupportedError

logger = sgtk.LogManager.get_logger(__name__)


class ShotgunCertificateHandler(object):
    """
    Class for managing Shotgun certificates required by websockets
    """

    def __init__(self):
        """
        Constructor

        :raises: :class:`ShotgunLocalHostCertNotSupportedError` if Shotgun site does
            not support the shotgunlocalhost certificate exchange feature.
        """
        self._bundle = sgtk.platform.current_bundle()

        # ensure we support this
        if not self._site_supports_shotgunlocalhost():
            raise ShotgunLocalHostCertNotSupportedError(
                "Shotgun site does not support Certificate download."
            )

        # ensure we have fresh certs
        self._retrieve_certificates_from_shotgun()

    @property
    def key_path(self):
        """
        Path to the private key file on disk
        """
        return os.path.join(self._get_shotgunlocalhost_keys_folder(), "server.key")

    @property
    def cert_path(self):
        """
        Path to the certificate file on disk
        """
        return os.path.join(self._get_shotgunlocalhost_keys_folder(), "server.crt")

    def _retrieve_certificates_from_shotgun(self):
        """
        Retrieves certificates from Shotgun.
        """
        logger.debug("Retrieving certificates from Shotgun")
        certs = self._bundle.shotgun._call_rpc("sg_desktop_certificates", {})
        self._write_cert(
            self.cert_path, certs["sg_desktop_cert"] + "\n" + certs["sg_desktop_ca"]
        )
        self._write_cert(self.key_path, certs["sg_desktop_key"])

    def _get_shotgunlocalhost_keys_folder(self):
        """
        Retrieves the location where the shotgunlocalhost.com keys will be downloaded to.

        :returns: Path to the folder where server.crt and server.key are.
        """
        return os.path.join(self._bundle.site_cache_location, "keys")

    def _site_supports_shotgunlocalhost(self):
        """
        Checks if the site supports the shotgunlocalhost cert exchange feature.

        :returns: True if supported, false if not
        """
        return self._bundle.shotgun.server_info.get(
            "shotgunlocalhost_browser_integration_enabled", False
        )

    def _write_cert(self, path, cert):
        """
        Writes a certificate to disk. Converts any textual \n into actual \n. This is required
        because certificates returned from Shotgun have their \n encoded as actual \n in the text.

        :param str path: Path to file that should be written.
        :param str cert: Certificate taken from Shotgun.
        """
        # the cert is a whole chunk of content. We use an arbitrary small
        # number here (e.g 5), in case there is some white space inside
        # the preference data.
        if len(cert) < 5:
            raise ValueError(
                "Invalid localhost certificate data in Shotgun! "
                "Please contact support."
            )

        logger.debug("Wrote shotgunlocalhost file %s" % path)
        # make sure folder exists
        folder = os.path.dirname(path)
        sgtk.util.filesystem.ensure_folder_exists(folder)
        # write content
        with open(path, "w") as fw:
            fw.write("\n".join(cert.split("\\n")))
