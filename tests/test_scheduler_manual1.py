from time import sleep
import pytest
from tests.helpers import *

from scheduler import Scheduler, SchedulerCallbacks
from configuration import Configuration
from device import Device
import datetime


scheduler: Scheduler = None

# Compare dictionnaries ignoring items order 
def cmp_dico(dico1:dict, dico2:dict, ignore_missing:bool=False) -> bool:
    if ignore_missing:
        if len(dico1) <= len(dico2): return False
    else:
        if len(dico1) != len(dico2): return False
    for elem in dico2:
        if not elem in dico1:
            return False
        if dico1[elem] != dico2[elem]:
            return False
    return True

#def teardown_module(module):

# The goal here is to test the handling of device manual mode :
# We test that we can enter an leave manual mode inside the same timeslot (no timeslot change),
# using the 'settings.manual_mode_reset_event' set to a numeric value (time based manual mode)
class TestSchedulerManualMode1:
    # SchedulerCallbacks
    def apply_devices_setpoints(self, setpoints: dict[str,tuple[float,bool]]):
        global scheduler
        if self.step == 1:
            sleep(0.2) # To be sure that the scheduler variable has been set
            # Step #1 : the 2 devices have a scheduled setpoint
            assert cmp_dico(setpoints, {'Dev1':(18.0,False), 'Dev2':(17.0,False)}, ignore_missing=True)
            self.devices['Dev1'].scheduled_setpoint = 18.0
            self.devices['Dev2'].scheduled_setpoint = 17.0
            self.step = 2

            # Now we put the 2 devices in manual mode (with a 15° setpoint)
            self.devices['Dev1'].setpoint = 15.0
            scheduler.on_device_setpoint(self.devices['Dev1'])
            self.devices['Dev2'].setpoint = 15.0
            scheduler.on_device_setpoint(self.devices['Dev2'])
            # Putting Dev1 after the end of the manual duration
            self.devices['Dev1'].manual_setpoint_date = datetime.datetime.now()-datetime.timedelta(hours=2)
            # The scheduler will detect a change on Dev1 and will call this callback on its own
        elif self.step == 2:
            # Step #2 :
            # - The device 'Dev1' must be back on its scheduled setpoint
            # - The device 'Dev2' must not change its setpoint (still in manual mode) 
            assert cmp_dico(setpoints, {'Dev1':(18.0,False), 'Dev2':(None,True)}, ignore_missing=True)
            self.devices['Dev1'].scheduled_setpoint = 18.0
            self.step = 3

            self.devices['Dev1'].setpoint = 18.0
            self.devices['Dev2'].manual_setpoint_date = datetime.datetime.now()-datetime.timedelta(hours=2)
            # The scheduler will detect a change on Dev2 and will call this callback on its own
        elif self.step == 3:
            # Step #3 : The device 'Dev2' must be back on its scheduled setpoint
            assert cmp_dico(setpoints, {'Dev1':(18.0,False), 'Dev2':(17.0,False)}, ignore_missing=True)
            self.devices['Dev1'].scheduled_setpoint = 18.0
            self.devices['Dev2'].scheduled_setpoint = 17.0

            self.step = -1
            scheduler.stop()

    def test_manual_mode_1(self):
        self.devices: dict[str, Device] = {}
        config:Configuration = Configuration(config_path, 'f1_')
        config_scheduler = config.get_scheduler()
        config_devices = config.get_devices()

        config_scheduler['active_schedule'] = 'test'
        config_scheduler['schedules'].append(
            {'alias':'test',
             'schedule_items':[
                 {'devices':['Dev1', 'Dev2'],
                  'timeslots_sets':[
                      {'dates':['1', '2', '3', '4', '5', '6', '7'],
                       'timeslots':[
                           {'start_time':datetime.time.fromisoformat('00:00:00'),
                            'temperature_set':'TSet1'}
                       ]}
                  ]}]})
        
        # Create devices from config_devices
        for devname in config_devices:
            devparams = config_devices[devname]
            prot = devparams['protocol']
            client_name = prot['name']
            protparams = prot['params']
            self.devices[devname] = Device(devname, devparams['entity'], "", client_name, protparams)

        self.step = 1
        manual_mode_reset_event = 1
        global scheduler
        scheduler = Scheduler(config_scheduler,
                        self, self.devices,
                        0,
                        manual_mode_reset_event,
                        0.2)
        
        scheduler.active_schedule_thread.join()
        scheduler = None
        assert self.step == -1
