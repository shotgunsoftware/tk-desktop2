# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#
import sgtk
import pprint
import datetime
from . import util
from . import requests

logger = sgtk.LogManager.get_logger(__name__)


class WebsocketsConnection(object):
    """
    Represents a websockets connection.

    This class implements the Shotgun websockets connection
    state management and handles communication.

    It has an associated :class:`WebsocketsServer` server as well as
    an associated :class:`ShotgunSiteHandler` which handles site
    specific services such as encryption of messages.

    The class implements a state machine which handles the various
    handshake states which are required in order to establish a
    secure connection with the server. Once a secure connection has
    been established, all command requests will be dispatched to the
    associated :class:`RequestRunner` instance which is responsible
    for the actual execution of the commands.
    """
    # shotgun protocol version to use.
    PROTOCOL_VERSION = 2

    # the various states which the connection can be in
    (AWAITING_HANDSHAKE, AWAITING_SERVER_ID_REQUEST, AWAITING_ENCRYPTED_REQUEST) = range(3)

    def __init__(self, ws_server, socket_id, shotgun_site, request_runner):
        """
        :param ws_server: Associated :class:`WebsocketsServer`
        :param socket_id: Unique id associated with this connection
        :param shotgun_site: Associated :class:`ShotgunSiteHandler`
        :param request_runner: Associated :class:`RequestRunner`
        """
        self._ws_server = ws_server
        self._request_runner = request_runner
        self._socket_id = socket_id
        self._shotgun_site = shotgun_site
        self._state = self.AWAITING_HANDSHAKE

    def __repr__(self):
        """
        String representation
        """
        return "<WebsocketsConnection %s - state %s>" % (self._socket_id, self._state)

    @property
    def shotgun(self):
        """
        Associated shotgun API connection
        """
        return self._shotgun_site.shotgun

    def process_message(self, message):
        """
        Callback which will be called whenever a message is received.

        :param str message: Raw message payload as sent by client.
        :raises: RuntimeError
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
        Sends an encrypted dictionary of data to the client.

        :param dict payload: Dictionary to transmit.
        :param request_id: The id of the request that the reply
            should be associated with. Each request coming from
            the client has an id and each reply should send the
            id of the request with which it is associated.
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
        # create json string and encrypt it.
        reply = util.create_reply(payload, self._shotgun_site.encrypt)
        self._ws_server.sendTextMessage(self._socket_id, reply)

    def _handle_protocol_handshake_request(self, message):
        """
        Processes the state where a client is trying to initiate
        a handshake. If successful, the state of the connection
        will become AWAITING_SERVER_ID_REQUEST.

        :param str message: Raw message from client
        :raises: RuntimeError on any error
        """
        logger.debug("Received handshake request: %s" % message)

        # the expected message is a raw text string which just
        # reads 'get_protocol_version'. The expected reply is an
        # unencrypted dictionary with key 'protocol_version'.

        if message == "get_protocol_version":
            reply = util.create_reply(
                {"protocol_version": self.PROTOCOL_VERSION}
            )
            self._ws_server.sendTextMessage(self._socket_id, reply)
            self._state = self.AWAITING_SERVER_ID_REQUEST
        else:
            raise RuntimeError("%s: Invalid request!" % self)

    def _handle_server_id_request(self, message):
        """
        Processes the state where the client is requesting
        the unique id associated with it, so that it can
        begin encrypting its communication. Once the unique
        id has been passed to the client, the state will shift
        to AWAITING_ENCRYPTED_REQUEST and further requests are
        expected to be encrypted.

        :param str message: Raw message from client
        :raises: RuntimeError on any error
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

        if "id" not in message_obj:
            raise RuntimeError("%s: Invalid request!" % self)

        if message_obj.get("command", {}).get("name") == "get_ws_server_id":
            reply = util.create_reply(
                {
                    "ws_server_id": self._shotgun_site.unique_server_id,
                    "timestamp": datetime.datetime.now(),
                    "protocol_version": self.PROTOCOL_VERSION,
                    "id": message_obj["id"],
                }
            )
            self._ws_server.sendTextMessage(self._socket_id, reply)
            # we are now ready to receive actual data
            self._state = self.AWAITING_ENCRYPTED_REQUEST
        else:
            raise RuntimeError("%s: Invalid request!" % self)

    def _handle_encrypted_request(self, message):
        """
        Main communication broker for the protocol.

        Handles messages arriving when the connection is in
        AWAITING_ENCRYPTED_REQUEST state. This state expects
        a fully initialized connection and each request sent
        and received being encrypted.

        Each message coming in will be turned into a
        :class:`WebsocketsRequest` object and passed to the
        associated :class:`RequestRunner` for actual execution.

        :param str message: Raw message from client
        :raises: RuntimeError on any error
        """
        # expected format from server (after encryption):
        #
        # {
        #     "id": 1,
        #     "timestamp": 1520903545674,
        #     "command": {
        #         "name": "<command name>",
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
        #

        # first decrypt message
        try:
            message = self._shotgun_site.decrypt(message)
        except Exception as e:
            raise RuntimeError("%s: Could not decrypt payload: %s" % (self, e))

        # Every message is expected to be in json format
        message_obj = util.parse_json(message)

        logger.debug("Received Shotgun request: %s" % pprint.pformat(message_obj))

        # We expect every response to have the protocol version set earlier
        if message_obj.get("protocol_version") != self.PROTOCOL_VERSION:
            raise RuntimeError("%s: Unexpected protocol version!" % self)

        # at this point we are handing over execution to the requests
        # implementation. Trap any exceptions and in the case
        # anything bubbles up, respond with a standard error
        # to the server on the following form:
        #
        # { retcode: -1, out: "", err: "error message" }
        #
        #
        try:
            # create a request
            request = requests.WebsocketsRequest.create(
                self,
                message_obj["id"],
                message_obj["command"]
            )

            # request that the request runner actions the request
            self._request_runner.execute(request)

        except Exception as e:
            logger.debug(
                "Exception raised while scheduling request %s" % pprint.pformat(message_obj),
                exc_info=True
            )
            data = {"retcode": -1, "out": "", "err": str(e)}
            self.reply(data, message_obj["id"])
