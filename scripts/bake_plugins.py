# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

# A script allowing to bake tk-desktop2 as self contained plugin.

from optparse import OptionParser
import os
import sys
import logging
import tempfile
import shutil
import subprocess

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(asctime)s %(funcName)s: %(message)s")

def bake_plugin(plugin_name, tk_core_path, output_path, debug=False):
    if debug:
        logging.setLevel(logging.DEBUG)
    logging.info("Baking plugin %s" % plugin_name)
    # First let's retrieve the plugin path
    plugin_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "plugins", plugin_name
    ))
    if not os.path.isdir(plugin_path):
        raise ValueError("Can't find %s path %s" % (plugin_name, plugin_path))

    manifest_path = os.path.join(plugin_path, "info.yml")
    if not os.path.exists(manifest_path):
        raise ValueError("Couldn't retrieve an info.yml file in %s" % manifest_path)

    # Check tk-core and import sgtk
    if not os.path.isdir(tk_core_path):
        raise ValueError("Can't access tk-core path %s" % tk_core_path)
    sgkt_path = os.path.abspath(os.path.join(tk_core_path, "python"))
    sys.path.insert(0, sgkt_path)

    import sgtk
    from tank_vendor import yaml
    from tank.descriptor import Descriptor, descriptor_uri_to_dict, descriptor_dict_to_uri
    from tank.bootstrap import constants as bootstrap_constants
    from tank.descriptor import create_descriptor

    with open(manifest_path, "rt") as fh:
        manifest_data = yaml.load(fh)
    # Retrieve the config information and ensure it is available and bakable.
    base_config_def = manifest_data.get("base_configuration")
    if not base_config_def:
        raise ValueError(
            "A base configuration needs to be defined in the manifest file."
        )
    if isinstance(base_config_def, str):
        # convert to dict so we can introspect
        base_config_uri_dict = descriptor_uri_to_dict(base_config_def)
        base_config_uri_str = base_config_def
    else:
        base_config_uri_dict = base_config_def
        base_config_uri_str = descriptor_dict_to_uri(base_config_def)
    logging.info(base_config_uri_dict)
    # Check the config required by the plugin, and turn it into a baked one.
    if base_config_uri_dict["type"] != bootstrap_constants.BAKED_DESCRIPTOR_TYPE:
        cfg_descriptor = create_descriptor(
            None,
            Descriptor.CONFIG,
            base_config_uri_dict,
            resolve_latest=bool("version" not in base_config_uri_dict)
        )
        cfg_descriptor.ensure_local()
        local_path = cfg_descriptor.get_path()
        if not local_path:
            raise ValueError("Unable to get a local copy of %s" % cfg_descriptor)
        baked_descriptor = {
            "type": bootstrap_constants.BAKED_DESCRIPTOR_TYPE,
            "path": local_path
        }
        manifest_data["base_configuration"] = baked_descriptor
        logging.info(manifest_data)
    try:
        temp_dir = tempfile.mkdtemp(suffix="tk-desktop2")
        temp_plugin_path = os.path.join(temp_dir, plugin_name)
        shutil.copytree(plugin_path, temp_plugin_path)
        logging.info("%s" % temp_dir)
        # Save the manifest file with a baked config.
        with open(os.path.join(temp_plugin_path, "info.yml"), "w") as pf:
            yaml.dump(manifest_data, pf)
        # And now really bake it with tk-core script
        bake_cmd = [
            sys.executable,
            os.path.join(tk_core_path, "developer", "build_plugin.py"),
            temp_plugin_path,
            output_path,
        ]
        logging.info("Running %s" % " ".join(bake_cmd))
        subprocess.check_call(bake_cmd)
    finally:
        pass

def main():
    usage = "usage: %prog [options]"
    parser = OptionParser(usage=usage)

    parser.add_option(
        "-t",
        "--tk-core",
        default=os.environ.get("TK_CORE_PATH"),
        dest="tk_core_path",
        help="Full path to a tk-core folder"
    )
    parser.add_option(
        "-o",
        "--output-path",
        dest="output_path",
        help="Full path to a folder where the plugins will be built"
    )
    parser.add_option(
        "-p",
        "--plugin",
        default="basic",
        help="The plugin to bake"
    )

    parser.add_option(
        "-d",
        "--debug",
        default=False,
        action="store_true",
        help="Enable debug logging"
    )
    options, _ = parser.parse_args()
    # Check arguments
    if not options.output_path:
        parser.error("An output path is required")
    if not options.tk_core_path:
        parser.error("A path to tk-core is needed")
    # Let's cook it!
    bake_plugin(
        options.plugin,
        os.path.abspath(options.tk_core_path),
        os.path.abspath(options.output_path)
    )

if __name__ == "__main__":
    """
    """
    main()
