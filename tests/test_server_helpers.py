import datetime
import json

from tests.fake_mqtt_client import FakeMQTTClient
from tests.helpers import *

cmd_topic = "heatingcontrol/command"
response_topic = "heatingcontrol/on_cmd_response"
is_alive_topic = "heatingcontrol/serverdata/is_alive"
on_scheduler_topic = "heatingcontrol/serverdata/on_scheduler"
on_devices_topic = "heatingcontrol/serverdata/on_devices"
on_entities_topic = "heatingcontrol/serverdata/on_entities"


class TSHelpers:
    def publish_new_entity(entity:str, name:str):
        FakeMQTTClient.send_fake_message_raw('heat', 'homeassistant/climate/'+entity+'/state')
        FakeMQTTClient.send_fake_message_raw('5.0', 'homeassistant/climate/'+entity+'/min_temp')
        FakeMQTTClient.send_fake_message_raw('35.0', 'homeassistant/climate/'+entity+'/max_temp')
        FakeMQTTClient.send_fake_message_raw('19.0', 'homeassistant/climate/'+entity+'/temperature')
        FakeMQTTClient.send_fake_message_raw('20.3', 'homeassistant/climate/'+entity+'/current_temperature')
        FakeMQTTClient.send_fake_message_raw(name, 'homeassistant/climate/'+entity+'/friendly_name')
        FakeMQTTClient.send_fake_message_raw(datetime.datetime.now(datetime.timezone.utc).isoformat(), 'homeassistant/climate/'+entity+'/last_updated')
        FakeMQTTClient.send_fake_message_raw('true', 'homeassistant/climate/'+entity+'/restored')

        entities = {item['srventity']:item['name'] for item in json.loads(FakeMQTTClient.instance.published_messages[on_entities_topic])}
        assert entity in entities

    def create_device(devname:str, entity:str, publish_entity:bool, add_device:bool, caplog):
        # We first need to publish a new device entity to trigger auto-discovery in server
        # This will make the entity available to add a device
        if publish_entity:
            TSHelpers.publish_new_entity(entity, devname)

        if add_device:
            devices = json.loads(FakeMQTTClient.instance.published_messages[on_devices_topic])
            nb_devices = len(devices)
            # Now we add a new device on this entity
            cmdname = "add_device"
            params = {"name": devname, "srventity": entity}
            FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
            assert response_topic in FakeMQTTClient.instance.published_messages
            assert '"status": "success"' in FakeMQTTClient.instance.published_messages[response_topic]
            check_no_error(caplog, True)

            # We check that the new device has been pushed to the remote clients by the server
            devices = json.loads(FakeMQTTClient.instance.published_messages[on_devices_topic])
            assert isinstance(devices, list)
            assert len(devices) == 1+nb_devices
            device = TSHelpers.find_device(devname)
            assert isinstance(device, dict)
            assert device['srventity'] == entity
            FakeMQTTClient.instance.published_messages.clear()
        
        caplog.records.clear()

    def change_active_schedule(schedule_name:str, caplog):
        caplog.records.clear()
        if schedule_name != '':
            # We check that the schedule exists
            assert TSHelpers.find_schedule(schedule_name)
        cmdname = "set_active_schedule"
        params = {"schedule_name": schedule_name}
        FakeMQTTClient.send_fake_message(cmdname, params, cmd_topic)
        assert response_topic in FakeMQTTClient.instance.published_messages
        assert '"status": "success"' in FakeMQTTClient.instance.published_messages[response_topic]
        assert '"cmd": "'+cmdname+'"' in FakeMQTTClient.instance.published_messages[response_topic]
        check_no_error(caplog, True)
        if schedule_name=='':
            assert TSHelpers.get_active_schedule_name() == None
        else:
            assert TSHelpers.get_active_schedule_name() == schedule_name

    def find_device(dev_name:str)->dict:
        devices = json.loads(FakeMQTTClient.instance.published_messages[on_devices_topic])
        if isinstance(devices, list):
            for device in devices:
                if isinstance(device, dict) and 'name' in device and device['name']==dev_name:
                    return device
        return None
    
    def count_dev_references(dev_name:str)->int:
        count:int = 0
        device = TSHelpers.find_device(dev_name)
        if device:
            count += 1
        
        schedule_names:list = ['']
        schedules = TSHelpers.get_schedules()
        for schedule in schedules:
            for schedule_item in schedule['schedule_items']:
                if dev_name in schedule_item['devices']:
                    count += 1
            schedule_names.extend(schedule['alias'])

        for schedule in schedule_names:
            temp_sets = TSHelpers.get_temp_sets(schedule)
            for temp_set in temp_sets:
                for device in temp_set['devices']:
                    if device['device_name'] == dev_name:
                        count += 1
        return count
    
    def find_tset(tset_name:str, schedule_name:str)->dict|None:
        scheduler = FakeMQTTClient.instance.published_messages_json[on_scheduler_topic]
        temp_sets = None
        if schedule_name=='':
            if 'temperature_sets' in scheduler:
                temp_sets = scheduler['temperature_sets']
        else:
            schedule = TSHelpers.find_schedule(schedule_name)
            if schedule and 'temperature_sets' in schedule:
                temp_sets = schedule['temperature_sets']
        if temp_sets:
            for tset in temp_sets:
                if tset['alias'] == tset_name:
                    return tset
        return None
    
    def get_all_timeslots(timeslotSet:dict)->list:
        ts:list = []
        if 'timeslots' in timeslotSet:
            ts.extend(timeslotSet['timeslots'])
        else:
            ts.extend(timeslotSet['timeslots_A'])
            ts.extend(timeslotSet['timeslots_B'])
        return ts
    
    def count_local_tempset_references(schedule:dict, tset_name:str)->int:
        count:int = 0
        for schedule_item in schedule['schedule_items']:
            for timeslot_set in schedule_item['timeslots_sets']:
                for timeslot in TSHelpers.get_all_timeslots(timeslot_set):
                    if timeslot['temperature_set'] == tset_name:
                        count += 1
        return count

    def count_global_tempset_references(tset_name:str)->int:
        """Count all references to global tset_name in schedules
        add +1 if tset_name exists in global temperature sets

        :param tset_name: _description_
        :type tset_name: str
        :return: _description_
        :rtype: int
        """
        count:int = 0
        for schedule in TSHelpers.get_schedules():
            look_in_schedule_items = True
            if 'temperature_sets' in schedule:
                for temp_set in schedule['temperature_sets']:
                    if temp_set['alias'] == tset_name:
                        # There is tset that has the same name, so we won't count references
                        # in this schedule items, for it references the local tset, not the global
                        look_in_schedule_items = False
                    if 'parent' in temp_set and temp_set['parent'] == tset_name:
                        count += 1
            if look_in_schedule_items:
                count += TSHelpers.count_local_tempset_references(schedule, tset_name)
            
        tset = TSHelpers.find_tset(tset_name, '')
        if tset:
            count += 1
        else:
            # Error in configuration : we have references to a unknown temperature set
            assert count == 0
        return count

    def get_schedules()->list:
        scheduler = FakeMQTTClient.instance.published_messages_json[on_scheduler_topic]
        if 'schedules' in scheduler:
            schedules = scheduler['schedules']
            if isinstance(schedules, list):
                return schedules
        return []
    
    def get_temp_sets(schedule_name:str='')->list:
        if schedule_name=='':
            data = FakeMQTTClient.instance.published_messages_json[on_scheduler_topic]
        else:
            data = TSHelpers.find_schedule(schedule_name)
        if data and 'temperature_sets' in data:
            res = data['temperature_sets']
            if isinstance(res,list):
                return res
        return []
    
    def find_schedule(schedule_name:str)->dict|None:
        schedules = TSHelpers.get_schedules()
        for schedule in schedules:
            if isinstance(schedule, dict) and 'alias' in schedule and schedule['alias']==schedule_name:
                return schedule
        return None
    
    def get_active_schedule_name()->str:
        scheduler = FakeMQTTClient.instance.published_messages_json[on_scheduler_topic]
        if 'active_schedule' in scheduler:
            return scheduler['active_schedule']
        return None
