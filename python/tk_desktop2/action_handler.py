# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import json
import sgtk
import time
import cPickle
import threading

from sgtk.platform.qt import QtCore, QtGui
from . import constants
from .shotgun_entity_path import ShotgunEntityPath

logger = sgtk.LogManager.get_logger(__name__)
external_config = sgtk.platform.import_framework(
    "tk-framework-shotgunutils", "external_config"
)


class ActionHandler(object):
    """
    Interface for UI interaction inside the desktop2 UI environment.

    Interacts with a single StandardItemModel inside the runtime
    environment which is populated with Toolkit menu actions
    depending on its current context.

    The model will signal out when new actions are needed (eg.
    when a user navigates in the UI) and this class will
    asynchronously fetch these actions. Actions are cross
    project and cross context and the external_config Shotgunutils
    module is utilized to retrieve the actions.
    """

    # QObject name for the C++ actions model
    ACTION_MODEL_OBJECT_NAME = "ToolkitActionModel"

    KEY_PICKLE_STR = "pickle_str"

    def __init__(self, plugin_id, base_config, task_manager):
        """
        Start up the engine's built in actions integration.

        This will attempt to bind against an ACTION_MODEL_OBJECT_NAME qt object
        which is assumed to be defined by C++ and establish a data exchange
        between this model and the engine.

        A Shotgun-utils external config instance is constructed to handle
        cross-context requests for actions and execution from the action model.

        :param str plugin_id: The plugin id associated with the runtime environment.
        :param str base_config: Descriptor URI for the config to use by default when
            no custom pipeline configs have been defined in Shotgun.
        :param task_manager: Task Manager to use for async processing.
        """
        self._bundle = sgtk.platform.current_bundle()

        # list of cached configuration objects, keyed by project id
        self._cached_configs = {}
        # last time stamp we checked for new configs (unix time)
        self._last_update_check = 0

        # actions integration state
        self._actions_model = None
        self._config_loader = None
        self._task_manager = None
        self._toolkit_manager = self._bundle.toolkit_manager

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
            self._actions_model.currentEntityPathChanged.connect(
                self._populate_context_menu
            )
            self._actions_model.actionTriggered.connect(self._execute_action)
            self._actions_model.currentProjectChanged.connect(
                self._preload_configurations
            )

            # hook up external configuration loader
            self._config_loader = external_config.ExternalConfigurationLoader(
                self._bundle.python_interpreter_path,
                self._bundle.name,
                plugin_id,
                base_config,
                task_manager,
                qt_parent,
            )
            self._config_loader.configurations_loaded.connect(
                self._on_configurations_loaded
            )
            self._config_loader.configurations_changed.connect(
                self._on_configurations_changed
            )

    def destroy(self):
        """
        Shuts down the handler
        """
        logger.debug("Begin shutting down action handler.")

        if self._actions_model:
            # make sure that we release signals from the C++ object
            logger.debug("Disconnecting engine from internal actions model.")
            self._actions_model.currentEntityPathChanged.disconnect(
                self._populate_context_menu
            )
            self._actions_model.actionTriggered.disconnect(self._execute_action)
            self._actions_model = None

        if self._config_loader:
            logger.debug("Shutting down command handler interface.")
            self._config_loader.shut_down()
            self._config_loader = None

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

        raise RuntimeError(
            "Could not retrieve internal object '%s'" % self.ACTION_MODEL_OBJECT_NAME
        )

    def _is_preloading_configs(self):
        """
        Checks whether configurations are being preloaded. This helps determine
        whether additional work should be done to request commands from those
        configs or not.

        :rtype: bool
        """
        # If we don't have an entity path, it's because we were pre-loading configurations
        # on a project change or initial launch. We don't need to do anything else.
        current_path = self._actions_model.currentEntityPath()

        if current_path is None or current_path == "":
            return True
        else:
            return False

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

        if current_path is None or current_path == "":
            return

        logger.debug("Requesting commands for %s" % current_path)

        # clear loading indicator
        self._actions_model.clear()

        sg_entity = ShotgunEntityPath.from_path(current_path)

        # If any of the configs we have cached are invalid, we're not going to
        # use the cached data. Instead, we'll query fresh from SG in case any
        # of those invalid configs have been fixed since the cache was built.
        cached_configs = self._cached_configs.get(sg_entity.project_id, [])
        invalid_configs = [c for c in cached_configs if not c.is_valid]

        if cached_configs and not invalid_configs:
            logger.debug("Configurations cached in memory.")
            # we got the configs cached!
            # ping a check to check that Shotgun pipeline configs are up to date
            cache_out_of_date = (
                time.time() - self._last_update_check
            ) > constants.CONFIG_CHECK_TIMEOUT_SECONDS
            if cache_out_of_date:
                # time to check with Shotgun if there are updates
                logger.debug(
                    "Requesting a check to see if any changes have happened in Shotgun."
                )
                self._last_update_check = time.time()
                # refresh - this may trigger a call to _on_configurations_changed
                self._config_loader.refresh_shotgun_global_state()

            # request that menu items are emitted for the currently
            # cached configurations.
            self._request_commands(
                sg_entity.project_id,
                sg_entity.secondary_entity_type,
                sg_entity.secondary_entity_id,
                sg_entity.primary_entity_type,
            )

        else:
            if invalid_configs:
                logger.debug(
                    "Configurations were cached, but contained at least one invalid config. "
                    "Requesting configuration data for project %s",
                    sg_entity.project_id,
                )
            else:
                logger.debug(
                    "No configurations cached. Requesting configuration data for "
                    "project %s",
                    sg_entity.project_id,
                )

            self._config_loader.request_configurations(sg_entity.project_id)

    def _preload_configurations(self, project_id):
        """
        Preloads pipeline configuration data for the given project id.

        :param int project_id: The entity id of the Project to preload.
        """
        logger.debug("Preloading configurations for project id=%s", project_id)
        self._config_loader.request_configurations(project_id)

    def _on_configurations_changed(self):
        """
        Indicates that the state of Shotgun has changed
        and that we should discard any cached configurations and reload them.
        """
        # This slot gets triggered on initial launch of the host application, and
        # in that case we're likely to not have a current entity path defined.
        # We can just return here if that's the case and it'll be no harm.
        current_path = self._actions_model.currentEntityPath()

        if current_path is None or current_path == "":
            return

        logger.debug("Shotgun has changed. Discarding cached configurations.")
        # our cached configuration objects are no longer valid
        # disconnect any signals so we no longer get callbacks from
        # these stale items
        for (project_id, configurations) in self._cached_configs.iteritems():
            for config in configurations:
                config.commands_loaded.disconnect(self._on_commands_loaded)
                config.commands_load_failed.disconnect(self._on_commands_load_failed)
        # and clear our internal tracking of these items
        self._cached_configs = {}

        # the model is not up to date so clear it
        self._actions_model.clear()

        # load in new configurations for current project
        sg_entity = ShotgunEntityPath.from_path(current_path)

        # reload our configurations
        # _on_configurations_loaded will triggered when configurations are loaded
        logger.debug(
            "Requesting new configurations for project id %s.", sg_entity.project_id
        )
        self._config_loader.request_configurations(sg_entity.project_id)

    def _on_configurations_loaded(self, project_id, configs):
        """
        Called when external configurations for the given project have been loaded.

        :param int project_id: Project id that configurations are associated with
        :param list configs: List of class:`ExternalConfiguration` instances belonging to the
            project_id.
        """
        logger.debug("New configs loaded for project id=%s", project_id)

        # Cache the configs!
        self._cached_configs[project_id] = configs

        logger.debug(
            "Config interpreter paths will be updated to: %s",
            self._bundle.python_interpreter_path
        )

        # wire up signals from our cached command objects
        for config in configs:
            # SG Create's Python interpreter path changes when the application is updated.
            # We need to make sure the interpreter referenced by the config object is
            # current, because it might have been cached to disk prior to the most recent
            # update of Create.
            config.interpreter = self._bundle.python_interpreter_path
            config.commands_loaded.connect(self._on_commands_loaded)
            config.commands_load_failed.connect(self._on_commands_load_failed)

        # If we're just doing a preload, then we can stop here since no one is asking
        # for a list of commands to be requested.
        if self._is_preloading_configs():
            logger.debug("No entity path is currently set. Not requesting commands!")
            return

        # and request commands to be loaded
        # make sure that the user hasn't switched to a different item
        # while things were loading
        sg_entity = ShotgunEntityPath.from_path(self._actions_model.currentEntityPath())

        if sg_entity.project_id == project_id:
            self._request_commands(
                project_id,
                sg_entity.secondary_entity_type,
                sg_entity.secondary_entity_id,
                sg_entity.primary_entity_type,
            )

    def _request_commands(self, project_id, entity_type, entity_id, link_entity_type):
        """
        Requests commands for the given entity.

        This is an asynchronous operation which will call
        _on_commands_loaded() upon completion.

        :param int project_id: Shotgun project id
        :param str entity_type: Shotgun entity type
        :param int entity_id: Shotgun entity id
        :param str link_entity_type: The type that the entity potentially
            is linked with. Tasks and notes are for example linked to other
            objects that they are associated with.
        """
        if not self._cached_configs.get(project_id, []):
            # this project has no configs associated
            # display 'nothing found' message
            # self._actions_model.appendAction(self.NO_ACTIONS_FOUND_LABEL, "", "")
            pass

        else:

            logger.debug(
                "Requesting commands for project %s, %s %s",
                project_id,
                entity_type,
                entity_id,
            )

            for config in self._cached_configs[project_id]:
                if not config.is_valid:
                    logger.warning(
                        "Configuration %s is not valid. Commands will not be loaded.",
                        config,
                    )
                    continue

                # If the tk_desktop2 engine cannot be found, fall back
                # on the tk-shotgun engine.
                config.request_commands(
                    project_id,
                    entity_type,
                    entity_id,
                    link_entity_type,
                    engine_fallback=constants.FALLBACK_ENGINE,
                )

    def _on_commands_loaded(
        self, project_id, entity_type, entity_id, link_entity_type, config, commands
    ):
        """
        Called when commands have been loaded for a given configuration.

        Note that this may be called several times for a project, if the project
        contains several pipeline configurations (for example dev sandboxes).

        :param int project_id: Project id associated with the request.
        :param str entity_type: Entity type associated with the request.
        :param int entity_id: Entity id associated with the request.
        :param str link_entity_type: Linked entity type associated with the request.
        :param config: Associated class:`ExternalConfiguration` instance.
        :param list commands: List of :class:`ExternalCommand` instances.
        """
        logger.debug(
            "Commands loaded for %s (type=%s, id=%s)", config, entity_type, entity_id
        )

        # If we don't have an entity path, it's because we were pre-loading commands
        # on a project change or initial launch. We don't need to do anything else.
        current_path = self._actions_model.currentEntityPath()

        if current_path is None or current_path == "":
            logger.debug("No entity path is currently set. Not setting new commands!")
            return

        # make sure that the user hasn't switched to a different item
        # while things were loading
        sg_entity = ShotgunEntityPath.from_path(current_path)

        if sg_entity.project_id != project_id:
            # user switched to other object. Do not update the menu.
            return

        # TODO - this is pending design and the UI and UI implementation
        # is also in motion so this implement is placeholder for the time being.
        # Need to add more robust support for grouping, loading and defaults.

        # legacy handling - TODO UX
        # for a final solution, perhaps we want to decorate these menu items
        # with a special marker to denote that they are legacy?
        #
        # if desktop-2 isn't installed in an environment, we
        # attempt to fall back onto tk-shotgun.
        # in that case, display a warning
        fallback_to_shotgun_engine = False
        for command in commands:
            if command.engine_name == "tk-shotgun":
                fallback_to_shotgun_engine = True
                break
        if fallback_to_shotgun_engine:
            logger.warning(
                "%s does not have a desktop-2 engine installed. Falling back on displaying "
                "the commands associated with the tk-shotgun engine instead." % config
            )

        # temporary workarounds to remove special 'system' commands which
        # will not execute well inside the multi process environment
        # TODO: This will need revisiting once we have final designs.
        SYSTEM_COMMANDS = ["Toggle Debug Logging", "Open Log Folder"]

        logger.debug(
            "Command interpreter paths will be updated to: %s",
            self._bundle.python_interpreter_path
        )

        for command in commands:

            if command.display_name in SYSTEM_COMMANDS:
                continue

            # Create's Python interpreter path might not be the same now as it was
            # when the command was cached to disk. This would happen if Create
            # auto-updated after the commands were cached.
            #
            # NOTE: we know there's an underlying problem here and that we have more
            # work to do in the future before we can bake Create's Python interpreter
            # into advanced config setups. Because it changes during an update, the
            # path referenced in a config will also have to update along with it. We
            # have the beginnings of a plan in place where we will reference a manifest
            # that directs us to a Python interpreter path that is current, and we'll
            # need to follow that when Toolkit is referencing the Python path. The
            # beginnings of that work is done (the manifest file exists now), but
            # we aren't quite ready to do the rest of the work required.
            command.interpreter = self._bundle.python_interpreter_path

            # populate the actions model with actions.
            # serialize the external command object so we can
            # unfold it at a later point without having to
            # retain any internal state
            if config.is_primary:
                display_name = command.display_name
            else:
                display_name = "%s: %s" % (
                    config.pipeline_configuration_name,
                    command.display_name,
                )

            # This is addressing a pretty extreme edge case, but if there are multiple
            # PC entities for the project referencing the exact same config on disk,
            # we end up with duplicate actions equal to the number of PC entities sharing
            # the same configuration. It's silly behavior, but culling the duplicated here
            # is the simplest solution, and works just fine.
            if not self._actions_model.findItems(display_name):

                # Convert the Python Pickle to a JSON string for easier processing from the C++ code
                pickle_string = command.serialize()
                pickle_dict = cPickle.loads(pickle_string)
                pickle_dict[self.KEY_PICKLE_STR] = pickle_string
                json_string = json.dumps(pickle_dict)

                self._actions_model.appendAction(
                    display_name, command.tooltip, json_string
                )

        self._actions_model.actionsChanged()

    def _on_commands_load_failed(
        self, project_id, entity_type, entity_id, link_entity_type, config, reason
    ):
        """
        Called when commands have been loaded for a given configuration.

        Note that this may be called several times for a project, if the project
        has got several pipeline configurations (for example dev sandboxes).

        :param int project_id: Project id associated with the request.
        :param str entity_type: Entity type associated with the request.
        :param int entity_id: Entity id associated with the request.
        :param str link_entity_type: Linked entity type associated with the request.
        :param config: Associated class:`ExternalConfiguration` instance.
        :param str reason: Details around the failure.
        """
        logger.debug("Commands failed to load for %s" % config)

        # make sure that the user hasn't switched to a different item
        # while things were loading
        sg_entity = ShotgunEntityPath.from_path(self._actions_model.currentEntityPath())

        if sg_entity.project_id != project_id:
            # user switched to other object. Do not update the menu.
            return

        # TODO - this is pending design and the UI and UI implementation
        # is also in motion so this implement is placeholder for the time being.
        # Need to add more robust support for grouping, loading and defaults.
        if config.is_primary:
            display_name = "Error Loading Actions"
        else:
            display_name = (
                "%s: Error Loading Actions" % config.pipeline_configuration_name
            )

        self._actions_model.appendAction(display_name, reason, "")

        logger.warning("Could not load actions for %s: %s" % (config, reason))

    def _execute_action_payload(self, command):
        """
        Helper method to execute command.
        Executes the given command instance and handles logging and errors.
        :param str command: ExternalCommand to execute
        """
        try:
            logger.debug("Executing %s", command)
            output = command.execute(pre_cache=True)
            logger.debug("Output from command: %s" % output)
        except Exception as e:
            # handle the special case where we are calling an older version of the Shotgun
            # engine which doesn't support PySide2 (v0.7.0 or earlier). In this case, trap the
            # error message sent from the engine and replace it with a more specific one:
            #
            # The error message from the engine looks like this:
            # Looks like you are trying to run a Sgtk App that uses a QT based UI,
            # however the Shotgun engine could not find a PyQt or PySide installation in
            # your python system path. We recommend that you install PySide if you want to
            # run UI applications from within Shotgun.
            if (
                "Looks like you are trying to run a Sgtk App that uses a QT based UI"
                in str(e)
            ):
                logger.error(
                    "The version of the Toolkit Shotgun Engine (tk-shotgun) you "
                    "are running does not support PySide2. Please upgrade your "
                    "configuration to use version v0.8.0 or above of the engine."
                )

            else:
                logger.error("Could not execute action: %s" % e)

    def _execute_action(self, path, action_str):
        """
        Triggered from the engine when a user clicks an action

        :param str path: entity path representation.
        :param unicode action_str: serialized :class:`ExternalCommand` payload.
        """
        # the 'loading' menu items currently don't have an action payload,
        # just an empty string.

        if action_str != "":

            # Get the Python pickle string out of the JSON obj comming from C++
            json_obj = json.loads(action_str)
            if self.KEY_PICKLE_STR not in json_obj:
                raise RuntimeError(
                    "The command's serialized Python data could not be found in the action's payload"
                    "that Shotgun Create provided. The action cannot be executed as a result."
                )

            # and create a command object.
            pickle_string = json_obj[self.KEY_PICKLE_STR]
            # pyside has mangled the string into unicode. make it utf-8 again.
            if isinstance(pickle_string, unicode):  # noqa
                pickle_string = pickle_string.encode("utf-8")

            action = external_config.ExternalCommand.deserialize(pickle_string)

            # Notify the user that the launch is occurring. If it's a DCC, there can
            # be some delay, and this will help them know that the work is happening.
            self._toolkit_manager.emitToast(
                "Launching %s..." % action.display_name,
                "info",
                False,  # Not persistent, meaning it'll stay for 5 seconds and disappear.
            )

            # run in a thread to not block
            thread_cb = lambda a=action: self._execute_action_payload(a)
            worker = threading.Thread(target=thread_cb)
            # setting daemon to True means the main process can quit
            # and the action process can live on
            worker.daemon = True
            worker.start()
