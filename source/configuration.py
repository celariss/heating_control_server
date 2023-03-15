__author__      = "Jérôme Cuq"

import datetime
import logging
import yaml
import sys, os
import copy

from common import *
from yaml.parser import ParserError
from yaml_tags import YamlTagsResolver
from errors import *

WEEKDAYS:list=['1','2','3','4','5','6','7']

class Configuration:
    def __init__(self, config_path:str, config_files_prefix:str):
        self.logger = logging.getLogger('hcs.configuration')
        self.config_filename = os.path.join(config_path, config_files_prefix+'configuration.yaml')
        self.default_config_filename = os.path.join(config_path, config_files_prefix+'default_configuration.yaml')
        self.secrets_filename = os.path.join(config_path, config_files_prefix+'secrets.yaml')
        self.format_version = 3
        self.load()
        
    ########################################################################################
    # save/load methods
    ########################################################################################
    def load(self):
        """
        :raises CfgError: in case of any error in configuration file
        """

        save:bool = False
        # We first choose the configuration file to load :
        # if self.config_filename does not exist or is old, we load the default configuration file
        default_conf_file_date = 0.
        conf_file_date = 0.
        if os.path.exists(self.config_filename):
            if os.path.exists(self.default_config_filename):
                default_conf_file_date = os.path.getmtime(self.default_config_filename)
            conf_file_date = os.path.getmtime(self.config_filename)
        filename = self.default_config_filename
        if conf_file_date>default_conf_file_date:
            filename = self.config_filename
        else:
            # In case we choose the default config file, we need to write
            # a new config file after loading process
            save = True
        if not os.path.exists(filename):
            raise CfgError(ECfgError.MISSING_FILE, '', None, {'filename':filename}, self.logger)

        self.logger.info("Opening configuration file '"+filename+"'")
        with open(filename, 'r', encoding='utf-8') as config_file:
            try:
                self.configdata = yaml.load(config_file,Loader=YamlTagsResolver.create_yaml_loader(self.secrets_filename))
            except ParserError as exc:
                raise CfgError(ECfgError.BAD_FILE_CONTENT, '', None, {'error':exc.problem}, self.logger)
            #self.configdata = yaml.safe_dump(config_file, allow_unicode=True)
            self.logger.debug('configuration file content : '+str(self.configdata))

        if self.__set_settings_default_values():
            save = True
        self.settings = self.configdata['settings']
        
        err:CfgError = self.__verify_config()
        if err: raise err

        if save:
            self.save()

    def save(self):
        self.logger.info("Saving configuration file '"+self.config_filename+"'")
        self.configdata['version'] = self.format_version
        # Before saving, we must convert back all dates in scheduler config
        configdata = copy.deepcopy(self.configdata)
        schedules = configdata['scheduler']['schedules']
        for schedule in schedules:
            Configuration.__convert_schedule_dates_to_string(schedule)
        with open(self.config_filename, 'w', encoding="utf-8") as config_file:
            yaml.dump(configdata, config_file, allow_unicode=True)

            
    ########################################################################################
    # Get methods
    ########################################################################################
    def get_auto_discovery(self) -> list[dict]:
        if 'auto_discovery' in self.settings:
            return self.settings['auto_discovery']
        return []

    def get_repeater_delay(self) -> int:
        return self.settings['message_repeater']['repeat_delay_sec']

    def get_scheduler_init_delai(self) -> int:
        return self.settings['scheduler']['init_delay_sec']
    
    def get_scheduler_manual_mode_reset_event(self) -> str:
        return self.settings['scheduler']['manual_mode_reset_event']
    
    def get_protocols(self, type=None):
        if 'protocols' in self.configdata:
            return self.configdata['protocols']
        else:
            return {}
    
    def get_devices(self)->dict:
        if 'devices' in self.configdata:
            return Configuration.listofdict_2_dict(self.configdata['devices'])
        else:
            return {}

    def get_device(self, device:str):
        config_devices:dict = self.get_devices()
        if device in config_devices:
            return config_devices[device]
        return None

    def get_scheduler(self):
        if 'scheduler' in self.configdata:
            return self.configdata['scheduler']
        return {}

    def get_schedules(self) -> list:
        return self.configdata['scheduler']['schedules']

    ### return None if given name is not a known schedule
    def get_schedule(self, schedule_name):
        for schedule in self.get_schedules():
            if schedule['alias'] == schedule_name:
                return schedule
        return None

    def get_remote_control(self):
        if 'remote_control' in self.configdata:
            return self.configdata['remote_control']
        return {}
        
    def get_temperature_sets(self, schedule_name:str='') -> list:
        scheduler_config:dict = self.get_scheduler()
        if schedule_name=='':
            if 'temperature_sets' in scheduler_config:
                return scheduler_config['temperature_sets']
        else:
            schedule_config = self.get_schedule(schedule_name)
            if schedule_config and 'temperature_sets' in schedule_config:
                return schedule_config['temperature_sets']
        return None

    def get_temperature_set(self, tempset_name:str, schedule_name:str='') -> dict:
        tempSets:list = self.get_temperature_sets(schedule_name)
        if tempSets:
            for tempset in tempSets:
                if tempset['alias'] == tempset_name:
                    return tempset
        return None


    ########################################################################################
    # Set/Change/Delete methods
    ########################################################################################
    def add_device(self, device_name:str, client_name:str, protocol_params:dict) -> CfgError:
        devices:dict = self.get_devices()
        if device_name in devices:
            return CfgError(ECfgError.DUPLICATE_UNIQUE_KEY, '/devices', None, {'key':device_name}, self.logger)
        self.configdata['devices'].append({device_name: {'protocol':{'name':client_name, 'params':protocol_params}}})
        self.save()
        return None

    def change_device_name(self, old_name:str, new_name:str) -> CfgError:
        if not self.get_device(new_name):
            device:dict = self.get_device(old_name)
            if not device:
                return CfgError(ECfgError.BAD_REFERENCE, '/devices', None, {'reference':old_name}, self.logger)

            for device in self.configdata['devices']:
                if old_name in device.keys():
                    device[new_name] = device.pop(old_name)
                    break

            Configuration.__rename_device_in_tempsets(self.get_temperature_sets(), old_name, new_name)
            for schedule in self.get_schedules():
                Configuration.__rename_device_in_tempsets(self.get_temperature_sets(schedule['alias']), old_name, new_name)
                for item in schedule['schedule_items']:
                    l:list = item['devices']
                    if old_name in l:
                        idx = l.index(old_name)
                        l.pop(idx)
                        l.insert(idx, new_name)
            self.save()
        else:
            return CfgError(ECfgError.DUPLICATE_UNIQUE_KEY, '/devices', None, {'key':new_name}, self.logger)
        return None

    def __rename_device_in_tempsets(tempsets:list, old_name:str, new_name:str):
        if tempsets:
            for tempset in tempsets:
                for dev in tempset['devices']:
                    if dev['device_name'] == old_name:
                        dev['device_name'] = new_name
                        break

    def set_devices_order(self, device_names:list) -> CfgError:
        for name in device_names:
            device:dict = self.get_device(name)
            if not device:
                return CfgError(ECfgError.BAD_REFERENCE, '/devices', None, {'reference':name}, self.logger)
        
        devices:dict = self.get_devices()
        if len(device_names) != len(devices):
            for name in devices:
                if not name in device_names:
                    return CfgError(ECfgError.MISSING_VALUE, '/devices', None, {'value':name}, self.logger)
        
        new_devices:list[dict] = []
        for devname in device_names:
            new_devices.append({devname:devices[devname]})
        self.configdata['devices'] = new_devices
        self.save()
        return None

    def set_schedule(self, schedule:dict) -> CfgError:
        cfgErr = self.__check_mandatories(schedule, ['alias', 'schedule_items'], '/scheduler/schedules', Configuration.get(schedule, 'alias', None))
        if cfgErr: return cfgErr
        name = schedule['alias']
        scheduleConfig = self.get_schedule(name)
        new:bool = not scheduleConfig
        save = scheduleConfig
        self.__set_schedule(name, schedule, new)
        cfgErr = self.__verify_scheduler_config()
        if not cfgErr:
            # there is no error detected
            self.save()
        else:
            if new:
                Configuration.__delete_schedule(self.get_schedules(), name)
            else:
                self.__set_schedule(name, save, False)
        return cfgErr

    def set_schedules_order(self, schedule_names:list) -> CfgError:
        new_schedules:list = []
        for name in schedule_names:
            schedule:dict = self.get_schedule(name)
            if not schedule:
                return CfgError(ECfgError.BAD_REFERENCE, '/scheduler/schedules', None, {'reference':name}, self.logger)
            new_schedules.append(schedule)
        
        schedules:list = self.get_schedules()
        if len(schedule_names) != len(schedules):
            for name in schedules:
                if not name in schedule_names:
                    return CfgError(ECfgError.MISSING_VALUE, '/scheduler/schedules', None, {'value':name}, self.logger)
        
        self.configdata['scheduler']['schedules'] = new_schedules
        self.save()
        return None

    def set_active_schedule(self, schedule_name) -> CfgError:
        if schedule_name=='':
            self.get_scheduler()['active_schedule'] = None
        else:
            schedule:dict = self.get_schedule(schedule_name)
            if schedule:
                self.get_scheduler()['active_schedule'] = schedule_name
            else:
                return CfgError(ECfgError.BAD_REFERENCE, '/scheduler/schedules', None, {'reference':schedule_name}, self.logger)

        self.save()
        return None

    def set_temperature_sets(self, temperature_sets:list[dict], schedule_name:str) -> CfgError:
        if schedule_name == '':
            return self._set_temperature_sets(temperature_sets, self.configdata['scheduler'])
        else:
            schedule = self.get_schedule(schedule_name)
            if schedule:
                return self._set_temperature_sets(temperature_sets, schedule)
        return CfgError(ECfgError.BAD_REFERENCE, '/scheduler/schedules', None, {'reference':schedule_name}, self.logger)

    def change_schedule_name(self, old_name:str, new_name:str) -> CfgError:
        if not self.get_schedule(new_name):
            schedule = self.get_schedule(old_name)
            if not schedule:
                return CfgError(ECfgError.BAD_REFERENCE, '/scheduler/schedules', None, {'reference':old_name}, self.logger)
            schedule['alias'] = new_name
            if self.get_scheduler()['active_schedule'] == old_name:
                self.get_scheduler()['active_schedule'] = new_name
            self.save()
        else:
            return CfgError(ECfgError.DUPLICATE_UNIQUE_KEY, '/scheduler/schedules', None, {'key':new_name}, self.logger)
        return None

    def delete_schedule(self, schedule_name:str) -> CfgError:
        if Configuration.__delete_schedule(self.get_schedules(), schedule_name)==False:
            return CfgError(ECfgError.BAD_REFERENCE, '/scheduler/schedules', None, {'reference':schedule_name}, self.logger)
        return None

    def change_temperature_set_name(self, old_name:str, new_name:str, schedule_name:str='') -> CfgError:
        node_path = '/scheduler/temperature_sets'
        if schedule_name != '':
            node_path = "/scheduler/schedules['"+schedule_name+"']/temperature_sets"
        tempSet:dict = self.get_temperature_set(old_name, schedule_name)
        if not tempSet:
            return CfgError(ECfgError.BAD_REFERENCE, node_path, None, {'reference':old_name}, self.logger)
        if self.get_temperature_set(new_name, schedule_name):
            return CfgError(ECfgError.DUPLICATE_UNIQUE_KEY, node_path, None, {'reference':new_name}, self.logger)

        # 1) we change the name of the temperature set
        tempSet['alias'] = new_name
        # 2) We change all references to this temperature set
        changed:bool = False
        if schedule_name=='':
            # The temperature is global : we need to change the references everywhere
            tempSets:list = self.get_temperature_sets(schedule_name)
            changed = Configuration._change_tempset_ref_in_tempsets(tempSets, old_name, new_name)
            for schedule_config in self.get_schedules():
                if Configuration._change_tempset_ref_in_schedule(schedule_config, old_name, new_name):
                    changed = True
        else:
            # We change references only in local schedule
            schedule_config = self.get_schedule(schedule_name)
            changed = Configuration._change_tempset_ref_in_schedule(schedule_config, old_name, new_name)

        if changed==True:
            CfgError = self.__verify_scheduler_config()
            if not CfgError:
                # there is no error detected
                self.save()
            else:
                self.load()
                return CfgError

        return None


    ########################################################################################
    # Configuration verification methods
    ########################################################################################
        
    # @return None if success, or a CfgError in case of missing mandatory nodes
    def __check_mandatories(self, dico:dict, keys_list:list, parent_node:str, node_key:str=None) -> CfgError:
        missing:list = get_missing_mandatories(dico, keys_list)
        if len(missing)>0:
            return CfgError(ECfgError.MISSING_NODES, parent_node, node_key, {'missing_children':missing}, self.logger)
        return None

    # @return None if the whole configuration is good to go, or ConfigError if any error
    def __verify_config(self) -> CfgError:
        cfgErr = self.__check_mandatories(self.configdata, ['settings', 'protocols', 'remote_control', 'scheduler', ('devices',True)], '/')
        if cfgErr: return cfgErr
        if not self.configdata['devices']:
            self.configdata['devices'] = []
        cfgErr = self.__verify_remote_control_config()
        if cfgErr: return cfgErr
        cfgErr = self.__verify_scheduler_config()
        if cfgErr: return cfgErr

        settings = self.configdata['settings']
        if 'auto_discovery' in settings:
            cfgErr = self.__check_mandatories(settings, ['auto_discovery'], '/settings')
            if cfgErr: return cfgErr

        return None

    # @return None if the 'remote_control' root configuration node is good to go, or ConfigError if any error
    def __verify_remote_control_config(self) -> CfgError:
        data = self.configdata['remote_control']
        if not isinstance(data,list):
            return CfgError(ECfgError.EXPECTED_LIST, '/remote_control', None, {}, self.logger)
        for item in data:
            cfgErr = self.__check_mandatories(item, ['name', 'protocol'], '/remote_control')
            if cfgErr: return cfgErr
            cfgErr = self.__check_mandatories(item['protocol'], ['name', 'params'], '/remote_control/protocol')
            if cfgErr: return cfgErr
        return None

    # @return None if the 'scheduler' root configuration node is good to go, or ConfigError if any error
    def __verify_scheduler_config(self) -> CfgError:
        scheduler_data = self.configdata['scheduler']
        cfgErr:CfgError = self.__check_mandatories(scheduler_data, [('active_schedule',True), ('schedules', True)], '/scheduler')
        if cfgErr: return cfgErr
        if not scheduler_data['schedules']:
            scheduler_data['schedules'] = []

        active_schedule_name = scheduler_data['active_schedule']
        active_schedule = self.get_schedule(active_schedule_name)
        if active_schedule_name and not active_schedule:
            return CfgError(ECfgError.BAD_REFERENCE, '/scheduler/active_schedule', None, {'reference':active_schedule_name}, self.logger)

        cfgErr = self.__verify_temperature_sets(None)
        if cfgErr: return cfgErr

        schedules = self.get_schedules()
        schedule_names = []
        for schedule in schedules:
            node_path:str = '/scheduler/schedules'
            cfgErr = self.__check_mandatories(schedule, ['alias', 'schedule_items'], node_path, Configuration.get(schedule, 'alias', None))
            if cfgErr: return cfgErr
            if schedule['alias'] in schedule_names:
                return CfgError(ECfgError.DUPLICATE_UNIQUE_KEY, node_path, schedule['alias'], {'reference':schedule['alias']}, self.logger)
            schedule_names.append(schedule['alias'])
            cfgErr = self.__verify_temperature_sets(schedule)
            if cfgErr: return cfgErr
            if len(schedule['schedule_items'])==0:
                return CfgError(ECfgError.EMPTY_LIST, node_path, schedule['alias'], {'child_node':'schedule_items'}, self.logger)
            idx = 0
            for schedule_item in schedule['schedule_items']:
                cfgErr = self.__verify_schedule_item(schedule_item, schedule, idx)
                if cfgErr: return cfgErr
                idx = idx+1
                            
            # converting start_time to datetime.time in the scheduler configuration
            cfgErr = self.__convert_schedule_dates_from_string(schedule)
            if cfgErr: return cfgErr
        
        # Detecting circular dependencies in temperature sets
        global_temp_sets = Configuration.get_dict_values_from_path(self.configdata, ['scheduler', 'temperature_sets'])
        for schedule in schedules:
            if 'temperature_sets' in schedule:
                node_path:str = "/scheduler/schedules['"+schedule['alias']+"']/temperature_sets"
                temp_sets = schedule['temperature_sets']
                cfgErr = self.__check_mandatories(temp_sets, ['alias', 'devices'], node_path)
                if cfgErr: return cfgErr
                temp_sets.extend(global_temp_sets)
                for temp_set in temp_sets:
                    aliases = self.__detect_circular_dependency(temp_sets, temp_set)
                    if aliases:
                        return CfgError(ECfgError.CIRCULAR_REF, node_path, None, {'aliases':aliases}, self.logger)
        return None

    def __verify_schedule_item(self, schedule_item:dict, schedule:dict, idx:int) -> CfgError:
        node_path = "/scheduler/schedules['"+schedule['alias']+"']/schedule_items"
        cfgErr = self.__check_mandatories(schedule_item, ['devices', 'timeslots_sets'], node_path, str(idx))
        if cfgErr: return cfgErr
        if len(schedule_item['devices'])==0:
            return CfgError(ECfgError.EMPTY_LIST, node_path, str(idx), {'child_node':'devices'}, self.logger)
           
        node_path = node_path+"['"+str(idx)+"']"
        for device in schedule_item['devices']:
            if not self.get_device(device):
                return CfgError(ECfgError.BAD_REFERENCE, node_path+'/devices', None, {'reference':device}, self.logger)
        weekdays = []
        tss_idx = 0
        for timeslots_set in schedule_item['timeslots_sets']:
            cfgErr = self.__verify_timeslots_set(timeslots_set, weekdays, schedule, idx, tss_idx)
            if cfgErr: return cfgErr
            tss_idx = tss_idx+1
        if len(weekdays)<7:
            missing = []
            for day in WEEKDAYS:
                if day not in weekdays: missing.append(day)
            return CfgError(ECfgError.MISSING_NODES, node_path+'/timeslots_sets', None, {'missing_children':missing}, self.logger)
        return None

    def __verify_timeslots_set(self, timeslots_set:dict, weekdays:list, schedule:dict, schedule_item_idx:int, tss_idx:int) -> CfgError:
        node_path = "/scheduler/schedules['"+schedule['alias']+"']/schedule_items['"+str(schedule_item_idx)+"']/timeslots_sets"
        cfgErr = self.__check_mandatories(timeslots_set, ['dates', 'timeslots'], node_path, str(tss_idx))
        if cfgErr: return cfgErr
        
        node_path = node_path+"['"+str(tss_idx)+"']"
        date_idx = 0
        for date in timeslots_set['dates']:
            if not date in WEEKDAYS:
                return CfgError(ECfgError.BAD_VALUE, node_path+'/dates', str(date_idx), {'value':date}, self.logger)
            if date in weekdays:
                return CfgError(ECfgError.DUPLICATE_UNIQUE_KEY, node_path+'/dates', None, {'key':date}, self.logger)
            date_idx = date_idx + 1
            weekdays.append(date)
        
        timeslots:list = timeslots_set['timeslots']
        ts_idx = 0
        for timeslot in timeslots:
            cfgErr = self.__check_mandatories(timeslot, ['start_time', 'temperature_set'], node_path+'/timeslots')
            if cfgErr: return cfgErr
            if not self.__find_temperature_set(timeslot['temperature_set'], schedule):
                return CfgError(ECfgError.BAD_REFERENCE, node_path+"/timeslots['"+str(ts_idx)+"']/temperature_set", None, {'reference':timeslot['temperature_set']}, self.logger)
        if len(timeslots)>0:
            timeslots[0]['start_time'] = '00:00:00'
        return None
    
    def __verify_temperature_sets(self, schedule:dict) -> CfgError:
        parent = schedule
        if schedule==None:
            parent = self.get_scheduler()
        if 'temperature_sets' in parent:
            tempsets:list = []
            node_path = '/scheduler/temperature_sets'
            if 'alias' in parent:
                node_path = "/scheduler/schedules['"+parent['alias']+"']/temperature_sets"
            for tempset in parent['temperature_sets']:
                cfgErr = self.__check_mandatories(tempset, ['alias', 'devices'], node_path, Configuration.get(tempset, 'alias', None))
                if cfgErr: return cfgErr
                if tempset['alias'] in tempsets:
                    return CfgError(ECfgError.DUPLICATE_UNIQUE_KEY, node_path, None, {'key':tempset['alias']}, self.logger)
                node_path_ = node_path+"['"+tempset['alias']+"']"
                tempsets.append(tempset['alias'])
                if 'inherited' in tempset:
                    if not self.__find_temperature_set(tempset['inherited'], schedule):
                        return CfgError(ECfgError.BAD_REFERENCE, node_path_+"/inherited", None, {'reference':tempset['inherited']}, self.logger)
                dev_idx = 0
                for device in tempset['devices']:
                    cfgErr = self.__check_mandatories(device, ['device_name', 'setpoint'], node_path_+"/devices", str(dev_idx))
                    if cfgErr: return cfgErr
                    if not self.get_device(device['device_name']):
                        return CfgError(ECfgError.BAD_REFERENCE, node_path_+"/devices['"+str(dev_idx)+"']/device_name", None, {'reference':device['device_name']}, self.logger)
                    value = toFloat(device['setpoint'], self.logger, "Invalid setpoint for device '"+device['device_name']+"' in temperature set '"+tempset['alias']+"': ")
                    if not value:
                        return CfgError(ECfgError.BAD_VALUE, node_path_+"/devices['"+str(dev_idx)+"']/setpoint", None, {'value':value}, self.logger)
                    device['setpoint'] = value
                    dev_idx = dev_idx + 1
        return None

    def __detect_circular_dependency(self, temp_sets, temp_set, previous_aliases = []) -> list:
        # test for circular dependency in list of aliases
        tempset_alias = temp_set['alias']
        if tempset_alias in previous_aliases:
            return previous_aliases
        previous_aliases.append(tempset_alias)

        # continue to browse hierarchy 
        if temp_set['inherits']:
            inherit_alias = temp_set['inherits']
            for set in temp_sets:
                if set['alias']==inherit_alias:
                    res = self.__detect_circular_dependency(temp_sets, set, previous_aliases)
                    if res: return res
        return None


    ########################################################################################
    # STATIC PUBLIC METHODS
    ########################################################################################
    
    def get(dico:dict, param:str, default_value:str):
        if param in dico:
            return dico[param]
        return default_value

    def get_dict_values_from_path(dico, list_path) -> list:
        while len(list_path)>0:
            if isinstance(dico,list):
                result = []
                for item in dico:
                    res = Configuration.get_dict_values_from_path(item, list_path.copy())
                    for r in res:
                        result.append(r)
                return result
            else:
                searchitem = list_path.pop(0)
                if searchitem in dico:
                    dico = dico[searchitem]
                else:
                    return []
        return [dico]

    def listofdict_2_dict(listofdict) -> dict:
        dict = {}
        for item in listofdict:
            name = list(item.keys())[0]
            value = list(item.values())[0]
            dict[name] = value
        return dict


    ###################################################################################
    ###                 PRIVATE MEMBERS
    ###################################################################################
    def _set_temperature_sets(self, temperature_sets:list[dict], parent:dict) -> CfgError:
        save = None
        if 'temperature_sets' in parent:
            save = parent['temperature_sets']
        parent['temperature_sets'] = temperature_sets
        cfgErr = self.__verify_scheduler_config()
        if not cfgErr:
            # there is no error detected
            self.save()
        else:
            if save:
                parent['temperature_sets'] = save
            else:
                parent.pop('temperature_sets')
            return cfgErr
        return None

    def __convert_schedule_date_from_string(self, time:object) -> datetime.time:
        if isinstance(time,datetime.time):
            return time
        result:datetime.time = None
        try:
            if isinstance(time, str):
                result = datetime.time.fromisoformat(time)
            elif isinstance(time, int):
                # We get there when the format HH:MM:SS has been misunderstood by yaml
                # typically when the quotes are missing and time is not beginning with 0
                # example : 16:30:30 will be interpreted as an angle in degrees and converted into an integer !
                if time>0 and time<=86400: # max 24 hours = 24*3600°
                    hour = (time//3600)
                    min = (time%3600)//60
                    sec:int = (time%3600)%60
                    time = str(hour).zfill(2) + ':' + str(min).zfill(2) + ':' + str(sec).zfill(2)
                    result = datetime.time.fromisoformat(time)
        except:
            pass
        return result

    def __convert_schedule_dates_from_string(self, schedule) -> CfgError:
        timeslots = Configuration.get_dict_values_from_path(schedule, ['schedule_items', 'timeslots_sets', 'timeslots'])
        for schedule_ts in timeslots:
            for time_slot in schedule_ts:
                if 'start_time' in time_slot:
                    start_time = self.__convert_schedule_date_from_string(time_slot['start_time'])
                    if not start_time:
                        return CfgError(ECfgError.BAD_VALUE, "/scheduler/schedules['"+schedule['alias']+"']/schedule_items/timeslots_sets/timeslots", None, {'value':time_slot['start_time']}, self.logger)
                    time_slot['start_time'] = start_time
        return None

    def __convert_schedule_dates_to_string(schedule):
        timeslots = Configuration.get_dict_values_from_path(schedule, ['schedule_items', 'timeslots_sets', 'timeslots'])
        for schedule in timeslots:
            for time_slot in schedule:
                if 'start_time' in time_slot:
                    if isinstance(time_slot['start_time'], datetime.time):
                        time_slot['start_time'] = time_slot['start_time'].isoformat()

    def _change_tempset_ref_in_tempsets(tempSets:list, old_name:str, new_name:str) -> bool:
        result:bool = False
        for tempSet in tempSets:
            if ('inherits' in tempSet) and tempSet['inherits']==old_name:
                tempSet['inherits'] = new_name
                result = True
        return result

    def _change_tempset_ref_in_schedule(schedule_config:dict, old_name:str, new_name:str) -> bool:
        result:bool = False
        if 'temperature_sets' in schedule_config:
            tempSets:list = schedule_config['temperature_sets']
            Configuration._change_tempset_ref_in_tempsets(tempSets, old_name, new_name)
        for schedule_item in schedule_config['schedule_items']:
            for timeslotSet in schedule_item['timeslots_sets']:
                for timeslot in timeslotSet['timeslots']:
                    if timeslot['temperature_set'] == old_name:
                        timeslot['temperature_set'] = new_name
                        result = True
        return result

    # @return True if any change occured in configuration data
    def __set_settings_default_values(self) -> bool:
        save:bool = False
        if not 'settings' in self.configdata:
            self.configdata['settings'] = {}
            save = True
        settings = self.configdata['settings']

        if not 'message_repeater' in settings:
            settings['message_repeater'] = {}
            save = True
        repeater = settings['message_repeater']
        repeat_delay = Configuration.get(repeater, 'repeat_delay_sec', None)
        if repeat_delay:
            repeat_delay = toInt(repeat_delay, self.logger, 'Invalid value in settings.message_repeater.repeat_delay_sec : ')
        if not repeat_delay:
            repeater['repeat_delay_sec'] = 120
            save = True

        if not 'scheduler' in settings:
            settings['scheduler'] = {}
            save = True
        scheduler = settings['scheduler']
        init_delay = Configuration.get(scheduler, 'init_delay_sec', None)
        if init_delay:
            init_delay = toInt(init_delay, self.logger, 'Invalid value in settings.scheduler.init_delay_sec : ')
        if not init_delay:
            scheduler['init_delay_sec'] = 20
            save = True
        manual_mode_reset_event = Configuration.get(scheduler, 'manual_mode_reset_event', None)
        if manual_mode_reset_event:
            if manual_mode_reset_event not in ["timeslot_change", "setpoint_change", "schedule_change"]:
                self.logger.error('Invalid value in settings.scheduler.manual_mode_reset_event : '+manual_mode_reset_event)
        if not manual_mode_reset_event:
            scheduler['manual_mode_reset_event'] = "setpoint_change"
            save = True

        return save

    def __get_schedule_index(self, schedule_name) -> int:
        i = 0
        for schedule in self.get_schedules():
            if schedule['alias'] == schedule_name:
                return i
            i+=1
        return -1

    # Replace a schedule by name, without any integrity control
    # @param createIfNew Add a new schedule in case the given schedule does not exist yet
    def __set_schedule(self, name, scheduleConfig:dict, createIfNew:bool):
        idx = self.__get_schedule_index(name)
        if idx>=0:
            self.get_schedules()[idx] = scheduleConfig
        elif createIfNew==True:
            self.get_schedules().append(scheduleConfig)

    def __delete_schedule(schedules:list, schedule_name:str) -> bool:
        idx:int = 0
        for schedule in schedules:
            if schedule['alias']==schedule_name:
                schedules.pop(idx)
                return True
            idx += 1
        return False
    
    def __find_temperature_set(self, tempset_name, schedule:dict):
        if schedule:
            if 'temperature_sets' in schedule:
                for tempset in schedule['temperature_sets']:
                    if tempset['alias']==tempset_name:
                        return tempset
        if 'temperature_sets' in self.get_scheduler():
            for tempset in self.get_scheduler()['temperature_sets']:
                if tempset['alias']==tempset_name:
                    return tempset
        return None