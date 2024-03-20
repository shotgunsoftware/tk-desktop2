# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import sgtk
import json
import collections

from tank_vendor import six

logger = sgtk.LogManager.get_logger(__name__)


def create_reply(data, encrypt_fn=None):
    """
    Create a JSON-formatted message to client.

    :param data: Object Data that will be converted to JSON.
    :param encrypt_fn: Optional Encryption method.
    :returns: Server ready payload
    """
    payload = json.dumps(data, ensure_ascii=True, default=_json_date_handler)
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
    return _convert(json.loads(payload))


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
    else:
        return json.JSONEncoder().default(obj)


def _convert(data):
    """
    Converts all keys/values in a dictionary from unicode
    to utf-8 encoded strings.

    :param dict data: Object with unicode values
    :returns: Object with only utf-8 encoded strings
    """

    if isinstance(data, six.string_types):
        return six.ensure_str(data)
    if isinstance(data, six.moves.collections_abc.Mapping):
        return {k: _convert(v) for k, v in data.items()}
    elif isinstance(data, six.moves.collections_abc.Iterable):
        return [_convert(v) for v in data]
    else:
        return data


def show_user_mismatch_popup(bundle, user_id):
    """
    Display modal popup to inform user about user
    website/shotgun Create mismatch

    :param bundle: Bundle object
    :param user_id: Id of user requesting a connection
    """
    # get current user details
    current_user = sgtk.util.get_current_user(bundle.sgtk)
    # get other user details
    user_details = bundle.shotgun.find_one(
        "HumanUser", [["id", "is", user_id]], ["name"]
    )
    warning_msg = (
        "A request was received from Flow Production Tracking from user %s. "
        "Create is currently authenticated with user %s, so the "
        "request was rejected. You will need to log into Flow Production Tracking "
        "Create as user %s in order to receive Toolkit menu actions "
        "or use local file linking for that user in Flow Production Tracking."
        % (user_details["name"], current_user["name"], user_details["name"])
    )
    logger.warning(warning_msg)
    from sgtk.platform.qt import QtGui, QtCore

    msg_box = QtGui.QMessageBox(
        QtGui.QMessageBox.Warning, "Requesting User Not Authenticated", warning_msg
    )
    msg_box.setWindowFlags(msg_box.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
    msg_box.exec_()


def show_site_mismatch_popup(bundle, site_url):
    """
    Display modal popup to inform user about site
    website/shotgun Create mismatch

    :param bundle: Bundle object
    :param site_url: Url of site requesting a connection
    """
    warning_msg = (
        "A request was received from %s. Create app is currently not logged into "
        "that site, so the request has been rejected. You will need to log into %s from "
        "Create app in order to see Toolkit menu actions or make use of local file "
        "linking on that Flow Production Tracking site." % (site_url, site_url)
    )
    logger.warning(warning_msg)
    from sgtk.platform.qt import QtGui, QtCore

    msg_box = QtGui.QMessageBox(
        QtGui.QMessageBox.Warning, "Not Authenticated", warning_msg
    )
    msg_box.setWindowFlags(msg_box.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
    msg_box.exec_()
