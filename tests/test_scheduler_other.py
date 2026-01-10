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

# The goal here is to test various public functions in scheduler class
class TestSchedulerOther:
    # SchedulerCallbacks
    def scheduler_error(self):
        assert False

    def apply_devices_setpoints(self, setpoints: dict[str,tuple[float,bool]]):
        global scheduler
        if self.step == 1:
            sleep(0.2) # To be sure that the scheduler variable has been set
            # Step #1 : some devices have a scheduled setpoint
            #           now the create and set new active schedule
            schedule:dict[str,dict[str,float]] = {'alias':'test2',
             'schedule_items':[
                 {'devices':['Dev3'],
                  'timeslots_sets':[
                      {'dates':['1', '2', '3', '4', '5', '6', '7'],
                       'timeslots':[
                           {'start_time':datetime.time.fromisoformat('00:00:00'),
                            'temperature_set':'TSet3'}
                       ]}
                  ]}]}
            self.step = 2
            scheduler.set_schedule(schedule)
            # Changing the active schedule will cause the scheduler to call this callback again
            scheduler.on_active_schedule_changed('test2')
            
            
            # The scheduler will take into account the new active schedule and call this callback on its own
        elif self.step == 2:
            # Step #2 : the 2 devices have a scheduled setpoint from the new active schedule
            assert cmp_dico(setpoints, {'Dev3':(19.0,False)}, ignore_missing=True)
            self.step = -1
            scheduler.stop()

        elif self.step == 11:
            sleep(0.2) # To be sure that the scheduler variable has been set
            self.step = 12
            # Step #11 : some devices have a scheduled setpoint
             # Step #1 : the 3 devices have a scheduled setpoint
            assert cmp_dico(setpoints, {'Dev1':(18.0,False), 'Dev2':(17.0,False), 'Dev3':(20.0,False)})
            #          now we simulate a device connection event
            scheduler.on_devices_connect(['Dev3', 'Dev4'])

        elif self.step == 12:
            # Step #12 : Only Dev3 device must be present in notified setpoints
            # no change on Dev1 and Dev2, and Dev4 is not in schedule, so no setpoint expected for them
            assert cmp_dico(setpoints, {'Dev3': (20.0, False)})
            self.step = -1
            scheduler.stop()

    def test_set_scheduler(self, caplog):
        # This test function tests the Scheduler.set_schedule public function
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
        check_no_error(caplog, False)

    def test_on_devices_connect(self, caplog):
        # This test function tests the Scheduler.on_devices_connect public function
        self.devices: dict[str, Device] = {}
        config:Configuration = Configuration(config_path, 'f1_')
        config_scheduler = config.get_scheduler()
        config_devices = config.get_devices()

        config_scheduler['active_schedule'] = 'test'
        config_scheduler['active_schedule'] = 'test'
        config_scheduler['schedules'].append(
            {'alias':'test',
             'schedule_items':[
                 {'devices':['Dev1', 'Dev2'],
                  'timeslots_sets':[
                      {'dates':['1', '2', '3', '4', '5', '6', '7'],
                       'timeslots':[
                           {'start_time':datetime.time.fromisoformat('00:00:00'),
                            'temperature_set':'TSet1'},
                           {'start_time':(datetime.datetime.now()+datetime.timedelta(seconds=1)).time(),
                            'temperature_set':'TSet2'},
                           {'start_time':(datetime.datetime.now()+datetime.timedelta(seconds=2)).time(),
                            'temperature_set':'TSet3'}
                       ]}
                  ]},
                  {'devices':['Dev3'],
                  'timeslots_sets':[
                      {'dates':['1', '2', '3', '4', '5', '6', '7'],
                       'timeslots':[
                           {'start_time':datetime.time.fromisoformat('00:00:00'),
                            'temperature_set':'TSet2'},
                           {'start_time':(datetime.datetime.now()+datetime.timedelta(milliseconds=1500)).time(),
                            'temperature_set':'TSet1'},
                           {'start_time':(datetime.datetime.now()+datetime.timedelta(milliseconds=2500)).time(),
                            'temperature_set':'TSet3'}
                       ]}
                  ]}]})
        
        # Create devices from config_devices
        for devname in config_devices:
            devparams = config_devices[devname]
            prot = devparams['protocol']
            client_name = prot['name']
            protparams = prot['params']
            self.devices[devname] = Device(devname, devparams['entity'], "", client_name, protparams)

        self.step = 11
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
        check_no_error(caplog, False)