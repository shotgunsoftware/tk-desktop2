# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import sgtk
import re
from .errors import PathParseError

logger = sgtk.LogManager.get_logger(__name__)


class ShotgunEntityPath(object):
    """
    Describes a Desktop 2 path that expresses a Shotgun entity.

    Examples of paths that are currently supported:

    - /projects/65/shots/862/tasks/568
    - /projects/450/assets/17128/tasks/10096
    """

    task_path_regex = re.compile(
        r"^/projects/(?P<project_id>[0-9]+)/(?P<entity_type>[a-z]+)/(?P<entity_id>[0-9]+)/tasks/(?P<task_id>[0-9]+)$"
    )

    def __init__(self, path):
        """
        :param str path: Shotgun entity path
        :raises: PathParseError on invalid paths
        """
        self._path = path
        self._project_id = None
        self._linked_entity_type = None
        self._linked_entity_id = None
        self._entity_id = None
        self._entity_type = None
        # parse the path
        self._parse_path(path)

    def __repr__(self):
        """String representation"""
        return "<ShotgunWiretapPath '%s'>" % self._path

    @property
    def project_id(self):
        """The Shotgun project id associated with this path"""
        return self._project_id

    @property
    def linked_entity_type(self):
        """The linked entity type, or None if entity is not linked"""
        return self._linked_entity_type

    @property
    def linked_entity_id(self):
        """The linked entity id, or None if entity is not linked"""
        return self._linked_entity_id

    @property
    def entity_type(self):
        """Associated entity type"""
        return self._entity_type

    @property
    def entity_id(self):
        """Associated entity id"""
        return self._entity_id

    def _parse_path(self, path):
        """
        Parses a shotgun entity path and populates
        the internal state of the object

        :param str path: entity path representation.
        :raises: PathParseError if the path cannot be parsed.
        """
        # format example:
        # /projects/65/shots/862/tasks/568
        # /projects/450/assets/17128/tasks/10096
        match = self.task_path_regex.match(path)

        if match is None:
            raise PathParseError("Format of Shotgun Entity Path '%s' is not supported." % path)

        # for now, we only support paths to tasks
        self._entity_type = "Task"

        # extract ids. Regex ensures that these are valid ints
        self._project_id = int(match.group("project_id"))
        self._linked_entity_id = int(match.group("entity_id"))
        self._entity_id = int(match.group("task_id"))

        # extract entity type - eg. 'shots'
        linked_entity_type = match.group("entity_type")
        # make sure it's all lower case
        linked_entity_type = linked_entity_type.lower()
        # convert to Shotgun style, drop plural 's' suffix and capitalize
        self._linked_entity_type = linked_entity_type[:-1].capitalize()


