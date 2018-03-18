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
import pprint
import datetime
from . import util
from . import requests


logger = sgtk.LogManager.get_logger(__name__)


class WebsocketsConnection(object):
    """
    A websockets connection
    """
    PROTOCOL_VERSION = 2
    (AWAITING_HANDSHAKE, AWAITING_SERVER_ID_REQUEST, AWAITING_ENCRYPTED_REQUEST) = range(3)

    def __init__(self, wss_server, socket_id, shotgun_site, request_runner):
        """
        """
        self._wss_server = wss_server
        self._request_runner = request_runner
        self._socket_id = socket_id
        self._shotgun_site = shotgun_site
        self._state = self.AWAITING_HANDSHAKE

    def __repr__(self):
        return "<WebsocketsConnection %s - state %s>" % (self._socket_id, self._state)

    def process_message(self, message):
        """
        Message callback
        """
        if isinstance(message, unicode):
            message = message.encode("utf8")

        if self._state == self.AWAITING_HANDSHAKE:
            self._handle_protocol_handshake_request(message)
        elif self._state == self.AWAITING_SERVER_ID_REQUEST:
            self._handle_server_id_request(message)
        elif self._state == self.AWAITING_ENCRYPTED_REQUEST:
            self._handle_encrypted_request(message)
        else:
            raise RuntimeError("Unknown state!")

    def reply(self, payload, request_id):
        """
        Sends an encrypted dictionary of data to the connected client
        """
        # return data to server
        payload = {
            "ws_server_id": self._shotgun_site.unique_server_id,
            "timestamp": datetime.datetime.now(),
            "protocol_version": self.PROTOCOL_VERSION,
            "id": request_id,
            "reply": payload,
        }

        logger.debug("Transmitting response: %s" % pprint.pformat(payload))
        reply = util.create_reply(payload, self._shotgun_site.encrypt)
        self._wss_server.sendTextMessage(self._socket_id, reply)

    def _handle_protocol_handshake_request(self, message):
        """
        """
        logger.debug("Received handshake request: %s" % message)

        if message == "get_protocol_version":
            reply = util.create_reply(
                {"protocol_version": self.PROTOCOL_VERSION}
            )
            self._wss_server.sendTextMessage(self._socket_id, reply)
            self._state = self.AWAITING_SERVER_ID_REQUEST
        else:
            raise RuntimeError("%s: Invalid request!" % self)

    def _handle_server_id_request(self, message):
        """
        """
        # expected format from server:
        #
        # {
        #     "id": 1,
        #     "timestamp": 1520903545674,
        #     "command": {
        #         "name": "get_ws_server_id",
        #         "data": {
        #             "user": {
        #                 "entity": {
        #                     "name": "John Smith",
        #                     "type": "HumanUser",
        #                     "id": 42,
        #                     "valid": "valid",
        #                     "status": "act"
        #                 },
        #                 "group_ids": [3],
        #                 "rule_set_display_name": "Admin",
        #                 "rule_set_id": 5
        #             }
        #         }
        #     }
        # }
        # Every message is expected to be in json format
        message_obj = util.parse_json(message)

        logger.debug("Received server id request: %s" % pprint.pformat(message_obj))

        # TODO: as early as possible, validate that the user creating the web request is
        # the same as the authenticated user for that shotgun site.


        if message_obj.get("command", {}).get("name") == "get_ws_server_id":
            reply = util.create_reply(
                {
                    "ws_server_id": self._shotgun_site.unique_server_id,
                    "timestamp": datetime.datetime.now(),
                    "protocol_version": self.PROTOCOL_VERSION,
                    "id": message_obj["id"],
                }
            )
            self._wss_server.sendTextMessage(self._socket_id, reply)
            # we are now ready to receive actual data
            self._state = self.AWAITING_ENCRYPTED_REQUEST
        else:
            raise RuntimeError("%s: Invalid request!" % self)

    def _handle_encrypted_request(self, message):
        """

        """
        # expected format from server (after encryption):
        #
        # {
        #     "id": 1,
        #     "timestamp": 1520903545674,
        #     "command": {
        #         "name": "xxxx",
        #         "data": {
        #             "user": {
        #                 "entity": {
        #                     "name": "John Smith",
        #                     "type": "HumanUser",
        #                     "id": 42,
        #                     "valid": "valid",
        #                     "status": "act"
        #                 },
        #                 "group_ids": [3],
        #                 "rule_set_display_name": "Admin",
        #                 "rule_set_id": 5
        #             }
        #         }
        #     }
        # }

        # now encrypted states
        try:
            message = self._shotgun_site.decrypt(message)
        except Exception as e:
            raise RuntimeError("%s: Could not decrypt payload!" % self)

        # Every message is expected to be in json format
        message_obj = util.parse_json(message)

        logger.debug("Received Shotgun request: %s" % pprint.pformat(message_obj))

        # We expect every response to have the protocol version set earlier
        if message_obj.get("protocol_version") != self.PROTOCOL_VERSION:
            raise RuntimeError("%s: Unexpected protocol version!" % self)

        # check that the sg authenticated user matches the currently authenticated
        # user here. If not, site switch.
        try:
            user_id = message_obj["command"]["data"]["user"]["entity"]["id"]
        except Exception as e:
            raise RuntimeError("%s: Missing user id from request!" % self)

        # TODO: implement site switching logic

        # create a request
        request = requests.WebsocketsRequest.create(
            message_obj["id"],
            message_obj["command"]
        )

        # request that the request runner actions the request
        self._request_runner.execute(request)


