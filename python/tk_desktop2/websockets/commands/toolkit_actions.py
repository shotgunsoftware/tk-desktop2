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
import json
import pprint
import datetime


logger = sgtk.LogManager.get_logger(__name__)


def list_actions(data):
    """
    :param dict data: Message payload.
    """


    actions = [
        dict(
            name="__core_info",
            title="Check for Core Upgrades...",
            deny_permissions=[],
            app_name="__builtin",
            group=None,
            group_default=False,
            engine_name="tk-shotgun",
        ),

        dict(
            name="__core_info",
            title="Maya 2016",
            deny_permissions=[],
            app_name="__builtin",
            group="Launch Maya",
            group_default=False,
            engine_name="tk-shotgun",
        ),

        dict(
            name="__core_info",
            title="Maya 2017",
            deny_permissions=[],
            app_name="__builtin",
            group="Launch Maya",
            group_default=True,
            engine_name="tk-shotgun",
        ),

    ]

    payload = {
        "err": "",
        "retcode": 0,
        "actions": {
            "Primary": {
                "config": "Primary",
                "actions": actions
            }
        },
        "pcs": ["Primary"],
    }
    return payload


def execute_action(data):
    """
    Pick single file or directory.

    :param dict data: Message payload. (no data expected)
    """
    return {}


