#!/usr/bin/env python3
# This script installs the heating control server on a running Home Assistant instance
# use '-h' option to see documentation
#
# NOTE: Please first install ruamel.yaml :
#       `pip install ruamel.yaml`
import argparse, sys, os
from helpers import *

def install_server_to_ha(params:dict):
    config_folder = params['HAConfigFolder']
    ha_config_file = os.path.join(config_folder,'configuration.yaml')
    ha_automations_file = os.path.join(config_folder,'automations.yaml')
    ha_serverconfig_file = os.path.join(config_folder,'heating_ctrl_configuration.yaml')
    ha_serverdefaultconfig_file = os.path.join(config_folder,'heating_ctrl_default_configuration.yaml')
    ha_serverlogfile = os.path.join(config_folder,'heating_ctrl_srv.log')
    ha_custom_components_folder = os.path.join(config_folder,'custom_components')
    ha_server_addon_folder = os.path.join(ha_custom_components_folder, 'heating_control_srv')
    ha_server_source_folder = os.path.join(ha_server_addon_folder,'heating_control_server')

    ###################################################################
    # PREREQUISITES
    ###################################################################
    log("Checking prerequisites...")
    # Verify that the target folder is actually HA config folder
    if (not os.path.exists(config_folder)) or \
       (not os.path.exists(ha_config_file)):
       log_error("Folder <"+config_folder+"> is not the shared config folder of Home Assistant")
    # Verify that target files are readable and their content is good
    yaml_check_file(ha_config_file)
    yaml_check_file(ha_automations_file)
    # Verify that target files are writable
    check_path_is_writable(ha_config_file)
    check_path_is_writable(ha_automations_file)

    ###################################################################
    # SERVER CONFIGURATION FILE
    ###################################################################
    log("Checking existing installation...")
    file_version = yaml_get_param('../heating_ctrl_default_configuration.yaml', 'version')
    ha_file_version = yaml_get_param(ha_serverconfig_file, 'version')
    ha_srv_version = get_python_global(os.path.join(ha_server_source_folder, 'controller.py'), 'VERSION')
    if ha_srv_version:
        log("A heating server (v"+str(ha_srv_version)+") is already installed")
    if ha_file_version:
        replace_config:bool = False
        cmp = file_version-ha_file_version
        if cmp!=0:
            if cmp<0:
                log("WARNING: The current installed server configuration file has a NEWER format than the one you are installing !")
            elif cmp>0:
                log("WARNING: The current installed server configuration file has an older format than the one you are installing")
            log("-> The current configuration must be erased")
            replace_config = True
        if not replace_config:
            res = ask_user("Do you want to [K]eep or [R]eplace your schedules and devices definition ?", ['k','r'], 'k')
            if res=='r': replace_config = True
        if replace_config:
            # We delete the config files
            remove_file(ha_serverdefaultconfig_file)
            remove_file(ha_serverconfig_file)
        else:
            # The existing config file becomes the default config file
            move_file(ha_serverconfig_file, ha_serverdefaultconfig_file)
    if os.path.exists(ha_serverdefaultconfig_file) and file_version==yaml_get_param(ha_serverdefaultconfig_file, 'version'):
        log("Patching configuration file '"+ha_serverdefaultconfig_file+"' ...")
    else:
        #log("Creating configuration file...")
        copy_file('../heating_ctrl_default_configuration.yaml', ha_serverdefaultconfig_file)
    yaml_set_params(ha_serverdefaultconfig_file,[
            ('protocols/mqtt/broker', params['MqttBroker']),
            ('protocols/mqtt/user', params['MqttUser']),
            ('protocols/mqtt/pwd', params['MqttPwd']),
            ('protocols/mqtt/port', params['MqttPort']),
            ('protocols/mqtt/ssl', params['MqttSsl'])
        ])
    remove_file(ha_serverlogfile, None)

    ###################################################################
    # HA CONFIGURATION FILE
    ###################################################################
    # Add the content of `./configuration.yaml` in HA `config/configuration.yaml`
    yaml_patch_file('./configuration.yaml', ha_config_file)
    # Add the content of `./automations.yaml` in HA `config/automations.yaml`
    yaml_patch_file('./automations.yaml', ha_automations_file, 'alias')

    ###################################################################
    # COPY OF CUSTOM COMPONENT FILES
    ###################################################################
    copy_folder('./custom_components/heating_control_srv/', ha_server_addon_folder)
    copy_folder('../source/', ha_server_source_folder, ignore=__python_ignore__)
    copy_folder('./custom_components/config/', config_folder, mergeDst=True)

    log("")
    log("##########################################")
    log("SUCCESS ! -> Please restart your HA server")
    log("##########################################")
    log("")

def __python_ignore__(src:str, names:list[str]) -> list[str]:
    if '__pycache__' in names:
        return ['__pycache__']
    return []

def main(argv):
    argParser = argparse.ArgumentParser(description="This script installs the heating control server on a running Home Assistant instance")
    argParser.add_argument("-p", "--param_file", help="Path to yaml file that contains install parameters", required=True, metavar="path", dest="param_file_path")
    args = argParser.parse_args()

    names:list[str] = ['HAConfigFolder', 'HAConfigFolder', 'MqttBroker', 'MqttUser', 'MqttPwd', ('MqttPort', int), ('MqttSsl', bool)]
    param_file_path = args.param_file_path
    params = read_ini_file(param_file_path, 'default', names)
    log("Install Parameters :")
    for name in params:
        log("  "+name+" = "+str(params[name]))
    log("")

    install_server_to_ha(params)

if __name__ == "__main__":
   main(sys.argv[1:])