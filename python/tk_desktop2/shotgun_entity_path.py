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
    Describes a Shotgun Create path that expresses a Shotgun entity.

    Examples of paths that are currently supported:

    - /
    - /Project/123

    - /Project/65/Shot/862/Task/568
    - /Project/450/Asset/17128/Task/10096
    - /Project/450/Asset/17128/Version/10096
    - /Project/65/Shot/862/Version/568

    Usage:

    > path_obj = ShotgunEntityPath.from_path('/')
    > path_obj.project_id
    None
    > path_obj.as_string()
    '/'

    > path_obj = ShotgunEntityPath()
    > path_obj.as_string()
    '/'
    > path_obj.set_project(123)
    > path_obj.as_string()
    '/Project/123'
    > path_obj.set_primary_entity('Shot', 123)
    > path_obj.as_string()
    '/Project/123/Shot/123'
    > path_obj.set_secondary_entity('Task', 222)
    > path_obj.as_string()
    '/Project/123/Shot/123/Task/222'
    """

    # the secondary entity types supported
    SUPPORTED_SECONDARY_ENTITY_TYPES = ["Version", "Task"]

    # note: shotgun entity type names cannot have unicode characters in them
    #       so we are not supporting that in this parser either.
    _PROJECT_REGEX = re.compile(r"^/Project/(?P<project_id>\d+)$")
    _PRIMARY_ENTITY_REGEX = re.compile(
        r"^/Project/(?P<project_id>\d+)/(?P<entity_type>\w+)/(?P<entity_id>[0-9]+)$"
    )
    _SECONDARY_ENTITY_REGEX = re.compile(
        r"^/Project/(?P<project_id>\d+)/(?P<entity_type>\w+)/(?P<entity_id>[0-9]+)/(?P<secondary_entity_type>\w+)/(?P<secondary_entity_id>\d+)$"
    )

    @classmethod
    def from_path(cls, path):
        """
        Constructs a shotgun path object given a path string

        :param str path: Path string to parse
        :returns: :class:`ShotgunEntityPath` instance
        :raises: ValueError on path parse failure
        """
        path_obj = cls()

        if cls._SECONDARY_ENTITY_REGEX.match(path):
            # path matches a project+primary+secondary format
            path_match = cls._SECONDARY_ENTITY_REGEX.match(path)
            path_obj.set_project(int(path_match.group("project_id")))
            path_obj.set_primary_entity(
                path_match.group("entity_type"), int(path_match.group("entity_id"))
            )
            path_obj.set_secondary_entity(
                path_match.group("secondary_entity_type"),
                int(path_match.group("secondary_entity_id")),
            )

        elif cls._PRIMARY_ENTITY_REGEX.match(path):
            # path matches a project+primary format
            path_match = cls._PRIMARY_ENTITY_REGEX.match(path)
            path_obj.set_project(int(path_match.group("project_id")))
            path_obj.set_primary_entity(
                path_match.group("entity_type"), int(path_match.group("entity_id"))
            )

        elif cls._PROJECT_REGEX.match(path):
            # path matches a project format
            path_match = cls._PROJECT_REGEX.match(path)
            path_obj.set_project(int(path_match.group("project_id")))

        elif path != "/":
            # does not match the root syntax nor any of the known forms above
            raise ValueError("Cannot parse path format '%s'" % (path,))

        return path_obj

    def __init__(self):
        """
        :param str path: Shotgun entity path
        :raises: PathParseError on invalid paths
        """
        self._project_id = None
        self._primary_entity_type = None
        self._primary_entity_id = None
        self._secondary_entity_id = None
        self._secondary_entity_type = None

    def __repr__(self):
        """String representation"""
        if self.is_valid():
            return "<ShotgunEntityPath '%s'>" % self.as_string()
        else:
            return "<ShotgunEntityPath 'PARTIAL'>"

    def as_string(self):
        """
        Returns the path as a string.

        :returns: Shotgun entity path as string
        :raises: Valuerror if path cannot be generated
        """
        # validate
        if self._secondary_entity_id and not self._primary_entity_id:
            raise ValueError("Secondary entity defined but no primary entity defined!")
        if self._primary_entity_id and not self._project_id:
            raise ValueError("Primary entity defined but no project defined!")

        # generate string
        if self._project_id is None:
            return "/"
        elif self._primary_entity_id is None:
            return "/Project/%d" % (self._project_id)
        elif self._secondary_entity_id is None:
            return "/Project/%d/%s/%d" % (
                self._project_id,
                self._primary_entity_type,
                self._primary_entity_id,
            )
        else:
            return "/Project/%d/%s/%d/%s/%d" % (
                self._project_id,
                self._primary_entity_type,
                self._primary_entity_id,
                self._secondary_entity_type,
                self._secondary_entity_id,
            )

    def is_valid(self):
        """
        Validation of the current object.

        :returns: True if path is valid, false if not
        """
        try:
            self.as_string()
        except ValueError:
            return False
        else:
            return True

    @property
    def project_id(self):
        """The Shotgun project id associated with this path"""
        return self._project_id

    @property
    def primary_entity_type(self):
        """Primary entity type, or None"""
        return self._primary_entity_type

    @property
    def primary_entity_id(self):
        """Primary entity id, or None"""
        return self._primary_entity_id

    @property
    def secondary_entity_type(self):
        """Secondary entity type, or None"""
        return self._secondary_entity_type

    @property
    def secondary_entity_id(self):
        """Secondary entity id, or None"""
        return self._secondary_entity_id

    def set_project(self, project_id):
        """
        Specify the project associated with this path

        :param int project_id: Project id to associate
        """
        self._project_id = project_id

    def set_primary_entity(self, entity_type, entity_id):
        """
        Specify the primary entity id associated with this path.

        :param str entity_type: Entity type to associate
        :param int entity_id: Entity id to associate
        """
        self._primary_entity_type = entity_type
        self._primary_entity_id = entity_id

    def set_secondary_entity(self, entity_type, entity_id):
        """
        Specify the secondary entity id associated with this path.

        The valid subset of entity types can be retrieved via
        self.SUPPORTED_SECONDARY_ENTITY_TYPES

        :param str entity_type: Entity type to associate
        :param int entity_id: Entity id to associate
        :raises: Valuerror if type is unsupported
        """
        if entity_type not in self.SUPPORTED_SECONDARY_ENTITY_TYPES:
            raise ValueError("Unsupported secondary entity type '%s'" % (entity_type,))
        self._secondary_entity_type = entity_type
        self._secondary_entity_id = entity_id
