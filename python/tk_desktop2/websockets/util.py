# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import sgtk
import json
import datetime
import collections

logger = sgtk.LogManager.get_logger(__name__)


def create_reply(data, encrypt_fn=None):
    """
    Create a JSON-formatted message to client.

    :param data: Object Data that will be converted to JSON.
    :param encrypt_fn: Optional Encryption method.
    :returns: Server ready payload
    """
    # ensure_ascii allows unicode strings.
    payload = json.dumps(
        data,
        ensure_ascii=False,
        default=_json_date_handler,
    ).encode("utf8")

    if encrypt_fn:
        payload = encrypt_fn(payload)

    return payload


def parse_json(payload):
    """
    Parses a json string in utf-8 encoded format,
    as expected from the Shotgun site.

    :param str payload: json payload
    :returns: Dictionary of values
    """
    # data is sent as utf-8 across the wire
    message_obj = json.loads(payload, encoding="utf-8")
    message_obj = _convert(message_obj)
    return message_obj


def create_error_reply(message, data=None, encrypt_fn=None):
    """
    Create a standard error json reply.

    Note: The error has no message id and therefore will lack
    traceability in the client.

    :param message: String Message describing the error.
    :param dict data: Optional information regarding the error.
    :param encrypt_fn: Optional Encryption method
    :returns: Server ready payload
    """
    error = {
        "error": True,
        "error_message": message,
    }
    if data:
        error["error_data"] = data
    return create_reply(error, encrypt_fn)


def _json_date_handler(obj):
    """
    JSON stringify python date handler from:
    http://stackoverflow.com/questions/455580/json-datetime-between-python-and-javascript

    :param obj: Object to serialize
    :returns: return a serializable version of obj or raise TypeError
    :raises: TypeError if a serializable version of the object cannot be made
    """
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    elif isinstance(obj, datetime.datetime):
        return obj.isoformat()
    else:
        return json.JSONEncoder().default(obj)


def _convert(data):
    """
    Converts all keys/values in a dictionary from unicode
    to utf-8 encoded strings.

    :param dict data: Object with unicode values
    :returns: Object with only utf-8 encoded strings
    """
    if isinstance(data, unicode):
        return data.encode("utf8")
    elif isinstance(data, collections.Mapping):
        return dict(map(_convert, data.iteritems()))
    elif isinstance(data, collections.Iterable):
        return type(data)(map(_convert, data))
    else:
        return data
