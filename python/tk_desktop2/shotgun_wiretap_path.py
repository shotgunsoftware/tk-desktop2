# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import sgtk
from .errors import PathParseError

logger = sgtk.LogManager.get_logger(__name__)


class ShotgunWiretapPath(object):
    """
    Describes a wiretap path that expresses a Shotgun entity.

    Examples of paths that are currently supported:

    - /projects/65/shots/862/tasks/568
    - /projects/450/assets/17128/tasks/10096
    """

    def __init__(self, path):
        """
        :param str path: Wiretap path
        """
        self._path = path
        self._project_id = None
        self._linked_entity_type = None
        self._linked_entity_id = None
        self._entity_id = None
        self._entity_type = None
        # parse the path
        self._parse(path)

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

    def _parse(self, path):
        """
        Parses a wiretap path and populates
        the internal state of the object

        :param str path: entity path representation.
        :raises: PathParseError if the path cannot be parsed.
        """
        # format example:
        # /projects/65/shots/862/tasks/568
        # /projects/450/assets/17128/tasks/10096
        tokens = path.split("/")
        if len(tokens) != 7:
            raise PathParseError("Path %s does not contain project/entity/task." % path)

        if tokens[1] != "projects":
            raise PathParseError(
                "Unexpected token %s: Found '%s', expected 'projects'." % (path, tokens[0])
            )

        if tokens[5] != "tasks":
            raise PathParseError(
                "Unexpected token %s: Found '%s', expected 'tasks'." % (path, tokens[4])
            )
        self._entity_type = "Task"

        # extract ids
        try:
            self._project_id = int(tokens[2])
            self._linked_entity_id = int(tokens[4])
            self._entity_id = int(tokens[6])
        except Exception, e:
            raise PathParseError("Path %s does not contain valid ids." % path)

        # extract entity type
        linked_entity_type = tokens[3]  # assets
        # convert to Shotgun style
        self._linked_entity_type = linked_entity_type[:-1].capitalize()

