# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import sys
import sgtk
from sgtk.platform import Engine
import sgtk
import time
import threading
import os
import sys

from .errors import PathParseError
from sgtk.platform.qt import QtCore, QtGui


logger = sgtk.LogManager.get_logger(__name__)
external_config = sgtk.platform.import_framework("tk-framework-shotgunutils", "external_config")


class ActionHandler(object):
    """
    Handles actions
    """
    # QObject name for the C++ actions model
    ACTION_MODEL_OBJECT_NAME = "ToolkitActionModel"

    # how often we check if Shotgun configs have changed
    CONFIG_CHECK_TIMEOUT_SECONDS = 30

    def __init__(self, engine_instance_name, plugin_id, base_config, task_manager):
        """
        Start up the engine's built in actions integration.

        This will attempt to bind against a ACTION_MODEL_OBJECT_NAME qt object
        which is assumed to be defined by C++ and establish a data exchange
        between this model and the engine.

        A Shotgun-utils external config instance is constructed to handle
        cross-context requests for actions and execution from the action model.

        :param str engine_instance_name: The instance name of the engine for
            which we should be retrieving commands.
        :param str plugin_id: The plugin id associated with the runtime environment.
        :param str base_config: Descriptor URI for the config to use by default when
            no custom pipeline configs have been defined in Shotgun.
        """
        logger.debug("Begin initializing action integrations")
        logger.debug("Engine instance name: %s" % engine_instance_name)
        logger.debug("Plugin id: %s" % plugin_id)
        logger.debug("Base config: %s" % base_config)

        # list of cached configuration objects, keyed by project id
        self._cached_configs = {}
        # last time stamp we checked for new configs (unix time)
        self._last_update_check = 0

        # actions integration state
        self._actions_model = None
        self._config_loader = None
        self._task_manager = None

        qt_parent = QtCore.QCoreApplication.instance()

        try:
            logger.debug("Attempting to bind against underlying C++ actions model...")
            self._actions_model = self._get_action_model()
        except RuntimeError:
            logger.error(
                "Could not retrieve internal ActionModel interface. "
                "No actions will be displayed."
            )
        else:
            # install signals from actions model
            self._actions_model.currentEntityPathChanged.connect(self._populate_context_menu)
            self._actions_model.actionTriggered.connect(self._execute_action)

            # hook up external configuration loader
            self._config_loader = external_config.ExternalConfigurationLoader(
                self._get_python_interpreter_path(),
                engine_instance_name,
                plugin_id,
                base_config,
                task_manager,
                qt_parent
            )
            self._config_loader.configurations_loaded.connect(self._on_configurations_loaded)
            self._config_loader.configurations_changed.connect(self._on_configurations_changed)

    def destroy(self):
        """
        """
        logger.debug("Begin shutting down action handler.")

        if self._actions_model:
            # make sure that we release signals from the C++ object
            logger.debug("Disconnecting engine from internal actions model.")
            self._actions_model.currentEntityPathChanged.disconnect(self._populate_context_menu)
            self._actions_model.actionTriggered.disconnect(self._execute_action)
            self._actions_model = None

        if self._config_loader:
            logger.debug("Shutting down command handler interface.")
            self._config_loader.shut_down()

    def _get_action_model(self):
        """
        Retrieves the internal C++ QT model that is used to render menus in Desktop2.

        :returns: QtoolkitActionsModel class (derived from QStandardItemModel)
        :raises: RuntimeError if not found
        """
        # TODO - this will change when we have more of an interface
        # in place on the C++ side as part of the toolkit baked bundling.
        if QtCore.QCoreApplication.instance() is None:
            raise RuntimeError("No QApplication found!")

        for q_object in QtCore.QCoreApplication.instance().children():
            if q_object.objectName() == self.ACTION_MODEL_OBJECT_NAME:
                return q_object
                break
        raise RuntimeError("Could not retrieve internal object '%s'" % self.ACTION_MODEL_OBJECT_NAME)

    def _path_to_entity(self, path):
        """
        Converts a desktop-2 style path to Shotgun entities

        :param str path: entity path representation.
        :returns: tuple with entity type, entity id and project id
        """
        # TODO - replace with internal VMR conversion method
        try:
            # format example:
            # /projects/65/shots/862/tasks/568
            entity_type = "Task"
            project_id = int(path.split("/")[2])
            entity_id = int(path.split("/")[-1])
            return entity_type, entity_id, project_id
        except Exception, e:
            raise PathParseError("Could not parse path '%s'" % path)

    def _populate_context_menu(self):
        """
        Populate the actions model with items suitable for the
        current context.

        It will check that Shotgun itself hasn't changed (for example someone
        updating the software entity, which would in turn affect the list of actions).
        this happens periodically, at the most every CONFIG_CHECK_TIMEOUT_SECONDS seconds
        and if a change is detected, _on_configurations_changed is asynchronously invoked.

        Configurations for the current project are then requested to generate
        actions suitable for the current context.
        """
        current_path = self._actions_model.currentEntityPath()
        logger.debug("Requesting commands for %s" % current_path)

        # clear loading indicator
        self._actions_model.clear()

        try:
            (entity_type, entity_id, project_id) = self._path_to_entity(
                current_path
            )
        except PathParseError:
            logger.warning("Cannot parse '%s'" % current_path)
            # don't know how to handle this entity.
            # return with a cleared menu.
            return

        if project_id in self._cached_configs:
            logger.debug("Configurations cached in memory.")
            # we got the configs cached!
            # ping a check to check that Shotgun pipeline configs are up to date
            cache_out_of_date = (time.time() - self._last_update_check) > self.CONFIG_CHECK_TIMEOUT_SECONDS
            if cache_out_of_date:
                # time to check with Shotgun if there are updates
                logger.debug("Requesting a check to see if any changes have happened in Shotgun.")
                self._last_update_check = time.time()
                # refresh - this may trigger a call to _on_configurations_changed
                self._config_loader.refresh_shotgun_global_state()

            # request that menu items are emitted for the currently
            # cached configurations.
            self._request_commands(project_id, entity_type, entity_id)

        else:
            logger.debug("No configurations cached. Requesting configuration data for project %s" % project_id)
            # we don't have any configuration objects cached yet.
            # request it - _on_configurations_loaded will be triggered when configurations are loaded
            self._add_loading_menu_indicator()
            self._config_loader.request_configurations(project_id)

    def _on_configurations_changed(self):
        """
        Indicates that the state of Shotgun has changed
        and that we should discard any cached configurations and reload them.
        """
        logger.debug("Shotgun has changed. Discarding cached configurations.")
        # our cached configuration objects are no longer valid
        # note: GC will disconnect any signals.
        self._cached_configs = {}

        # load in new configurations for current project
        (entity_type, entity_id, project_id) = self._path_to_entity(
            self._actions_model.currentEntityPath()
        )
        # reload our configurations
        # _on_configurations_loaded will triggered when configurations are loaded
        logger.debug("Requesting new configurations for %s." % project_id)
        self._config_loader.request_configurations(project_id)

    def _on_configurations_loaded(self, project_id, configs):
        """
        Called when external configurations for the given project have been loaded.

        :param int project_id: Project id that configurations are associated with
        :param list configs: List of ExternalConfiguration instances belonging to the
            project_id.
        """
        logger.debug("New configs loaded for project %s" % project_id)

        # clear any loading indication
        self._remove_loading_menu_indicator()

        # and request commands to be loaded
        # make sure that the user hasn't switched to a different item
        # while things were loading
        (entity_type, entity_id, curr_project_id) = self._path_to_entity(
            self._actions_model.currentEntityPath()
        )

        # cache our configs
        if len(configs) > 0:
            self._cached_configs[project_id] = configs

            # wire up signals from our cached command objects
            for config in configs:
                config.commands_loaded.connect(self._on_commands_loaded)
                config.commands_load_fail.connect(self._on_commands_load_failed)

            if curr_project_id == project_id:
                self._request_commands(project_id, entity_type, entity_id)

        else:
            if curr_project_id == project_id:
                logger.debug(
                    "No configuration associated with project id %s" % project_id
                )

    def _request_commands(self, project_id, entity_type, entity_id):
        """
        Requests commands for the given entity.

        This is an asynchronous operation which will call
        _on_commands_loaded() upon completion.

        :param int project_id: Shotgun project id
        :param str entity_type: Shotgun entity type
        :param int entity_id: Shotgun entity id
        """
        logger.debug(
            "Requesting commands for project %s, %s %s" % (project_id, entity_type, entity_id)
        )
        for config in self._cached_configs[project_id]:

            # indicate that we are loading data for this config
            self._add_loading_menu_indicator(config)

            config.request_commands(
                project_id,
                entity_type,
                entity_id,
                link_entity_type=None  # TODO: <-- fix
            )

    def _on_commands_loaded(self, project_id, config, commands):
        """
        Called when commands have been loaded for a given configuration.

        Note that this may be called several times for a project, if the project
        has got several pipeline configurations (for example dev sandboxes).

        :param int project_id: Project id associated with the request.
        :param config: Associated ExternalConfiguration instance.
        :param list commands: List of ExternalCommand instances.
        """
        # make sure that the user hasn't switched to a different item
        # while things were loading
        (_, _, curr_project_id) = self._path_to_entity(
            self._actions_model.currentEntityPath()
        )
        if curr_project_id != project_id:
            # user switched to other object. Do not update the menu.
            return

        # TODO - this is pending design and the UI and UI implementation
        # is also in motion so this implement is placeholder for the time being.
        # Need to add more robust support for grouping, loading and defaults.

        for command in commands:
            # populate the actions model with actions.
            # serialize the external command object so we can
            # unfold it at a later point without having to
            # retain any internal state
            if config.is_primary:
                display_name = command.display_name
            else:
                display_name = "%s: %s" % (config.pipeline_configuration_name, command.display_name)

            # temporary workarounds to remove special 'system' commands which
            # will not execute well inside the multi process environment
            # TODO: This will need revisiting once we have final designs.
            SYSTEM_COMMANDS = ["Toggle Debug Logging", "Open Log Folder"]
            if command.display_name in SYSTEM_COMMANDS:
                continue

            self._actions_model.appendAction(
                display_name,
                command.tooltip,
                command.serialize()
            )

        # remove any loading message associated with this batch
        self._remove_loading_menu_indicator(config)

    def _on_commands_load_failed(self, project_id, config, reason):
        """
        Called when commands have been loaded for a given configuration.

        Note that this may be called several times for a project, if the project
        has got several pipeline configurations (for example dev sandboxes).

        :param int project_id: Project id associated with the request.
        :param config: Associated ExternalConfiguration instance.
        :param str reason: Details around the failure.
        """
        # make sure that the user hasn't switched to a different item
        # while things were loading
        (_, _, curr_project_id) = self._path_to_entity(
            self._actions_model.currentEntityPath()
        )
        if curr_project_id != project_id:
            # user switched to other object. Do not update the menu.
            return

        # TODO - this is pending design and the UI and UI implementation
        # is also in motion so this implement is placeholder for the time being.
        # Need to add more robust support for grouping, loading and defaults.
        if config.is_primary:
            display_name = "Error Loading Actions"
        else:
            display_name = "%s: Error Loading Actions" % config.pipeline_configuration_name

        self._actions_model.appendAction(display_name, reason, "")

        logger.error("Could not load actions for %s: %s" % (config, reason))

        # remove any loading message associated with this batch
        self._remove_loading_menu_indicator(config)


    def _execute_action(self, path, action_str):
        """
        Triggered from the engine when a user clicks an action

        :param str path: entity path representation.
        :param unicode action_str: serialized :class:`ExternalCommand` payload.
        """
        # the 'loading' menu items currently don't have an action payload,
        # just an empty string.
        if action_str != "":
            # pyside has mangled the string into unicode. make it utf-8 again.
            if isinstance(action_str, unicode):
                action_str = action_str.encode("utf-8")

            # and create a command object.
            action = external_config.ExternalCommand.deserialize(action_str)
            # run in a thread to not block
            worker = threading.Thread(target=action.execute)
            worker.daemon = True
            worker.start()

    def _add_loading_menu_indicator(self, configuration=None):
        """
        Adds a menu item saying "loading" for the given config.

        :param configuration: :class:`ExternalConfiguration` to create
            loading indicator for or None if a general indicator
            should be created
        """
        # TODO - this is pending design and the UI and UI implementation
        # is also in motion so this implement is placeholder for the time being.
        # Need to add more robust support for grouping, loading and defaults.
        if configuration is None:
            self._actions_model.appendAction("Loading Configurations...", "", "")
        elif configuration.is_primary:
            self._actions_model.appendAction("Loading Actions...", "", "")
        else:
            self._actions_model.appendAction(
                "%s: Loading Actions..." % configuration.pipeline_configuration_name,
                "",
                ""
            )

    def _remove_loading_menu_indicator(self, configuration=None):
        """
        Removes a loading message for the given config.

        :param configuration: :class:`ExternalConfiguration` to remove
            load indicator for. If set to None, the general indicator
            is removed.
        """
        # TODO - this is pending design and the UI and UI implementation
        # is also in motion so this implement is placeholder for the time being.
        # Need to add more robust support for grouping, loading and defaults.
        if configuration is None:
            label = "Loading Configurations..."
        elif configuration.is_primary:
            label = "Loading Actions..."
        else:
            label = "%s: Loading Actions..." % configuration.pipeline_configuration_name

        root_item = self._actions_model.invisibleRootItem()
        for idx in range(self._actions_model.rowCount()):
            item = self._actions_model.item(idx)
            if item.text() == label:
                # remove it
                root_item.takeRow(idx)
                break

    def _get_python_interpreter_path(self):
        """
        Returns the path to the desktop2 python interpreter

        :returns: Path to python
        """
        # TODO: centralize and fix
        if sys.platform == "win32":
            return os.path.abspath(os.path.join(sys.prefix, "python.exe"))
        else:
            return os.path.abspath(os.path.join(sys.prefix, "bin", "python"))
