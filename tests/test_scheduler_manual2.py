from time import sleep
import pytest
from tests.helpers import *

from scheduler import Scheduler, SchedulerCallbacks
from configuration import Configuration
from device import Device
import datetime


scheduler: Scheduler = None

# Compare dictionnaries ignoring items order 
def cmp_dico(dico1:dict, dico2:dict) -> bool:
    if len(dico1) != len(dico2): return False
    for elem in dico1:
        if not elem in dico2:
            return False
        if dico1[elem] != dico2[elem]:
            return False
    return True

#def teardown_module(module):

# The goal here is to test the handling of device manual mode :
# We test that we can enter an leave manual mode between 2 timeslots :
#   1) using the 'settings.manual_mode_reset_event' set to a numeric value (time based manual mode)
#   2) using the 'settings.manual_mode_reset_event' set to either 'timeslot_change' or 'setpoint_change'
class TestSchedulerManualMode2:
    # SchedulerCallbacks
    def scheduler_error(self):
        assert False

    def apply_devices_setpoints(self, setpoints: dict[str,tuple[float,bool]]):
        global scheduler
        if self.step == 1:
            sleep(0.2) # To be sure that the scheduler variable has been set
            # Step #1 : the 3 devices have a scheduled setpoint
            assert cmp_dico(setpoints, {'Dev1':(18.0,False), 'Dev2':(17.0,False), 'Dev3':(20.0,False)})
            self.devices['Dev1'].scheduled_setpoint = 18.0
            self.devices['Dev2'].scheduled_setpoint = 17.0
            self.devices['Dev3'].scheduled_setpoint = 20.0
            self.step = 2

            # Now we put the Dev1 device in manual mode (with a 15° setpoint)
            self.devices['Dev1'].setpoint = 15.0
            scheduler.on_device_setpoint(self.devices['Dev1'])
            # We wait until a timeslot change. The scheduler will detect a change for Dev2 setpoint
        elif self.step == 2:
            # Step #2 :
            # - The device 'Dev1' is still in manual mode
            # - The device 'Dev2' has a new setpoint
            assert cmp_dico(setpoints, {'Dev1':(None,True), 'Dev2':(19.0,False), 'Dev3':(20.0,False)})
            self.devices['Dev2'].scheduled_setpoint = 19.0
            self.devices['Dev3'].scheduled_setpoint = 20.0
            self.step = 3

            # Putting Dev1 after the end of the manual duration
            self.devices['Dev1'].manual_setpoint_date = datetime.datetime.now()-datetime.timedelta(hours=2)
            # The scheduler will detect a change on Dev1 and will call this callback on its own
        elif self.step == 3:
            # Step #3 : The device 'Dev1' must be back on its scheduled setpoint (on second timeslot)
            assert cmp_dico(setpoints, {'Dev1':(16.0,False), 'Dev2':(19.0,False), 'Dev3':(20.0,False)})
            self.step = -1
            scheduler.stop()
        
        # The steps here after test the manual_mode_reset_event set to 'timeslot_change'
        elif self.step == 11:
            sleep(0.2) # To be sure that the scheduler variable has been set
            # Step #11 : the 3 devices have a scheduled setpoint
            assert cmp_dico(setpoints, {'Dev1':(18.0,False), 'Dev2':(17.0,False), 'Dev3':(20.0,False)})
            self.devices['Dev1'].scheduled_setpoint = 18.0
            self.devices['Dev2'].scheduled_setpoint = 17.0
            self.devices['Dev3'].scheduled_setpoint = 20.0
            self.step = 12

            # Now we put the Dev1 device in manual mode (with a 15° setpoint)
            self.devices['Dev1'].setpoint = 15.0
            scheduler.on_device_setpoint(self.devices['Dev1'])
            # We wait until a timeslot change. The scheduler will detect a change for devices #1 and #2
        elif self.step == 12:
            # Step #12 : Both devices must be back on scheduled setpoints (on second timeslot)
            assert cmp_dico(setpoints, {'Dev1':(16.0,False), 'Dev2':(19.0,False), 'Dev3':(20.0,False)})
            self.devices['Dev1'].scheduled_setpoint = 16.0
            self.devices['Dev2'].scheduled_setpoint = 19.0
            self.devices['Dev3'].scheduled_setpoint = 20.0
            self.step = 13

            # Now we put the Dev1 device in manual mode once again (with a 15° setpoint)
            self.devices['Dev1'].setpoint = 15.0
            scheduler.on_device_setpoint(self.devices['Dev1'])
            # We wait until a timeslot change (for Dev3). The scheduler will detect a change for Dev3.
        elif self.step == 13:
            # Step 13 : Dev1 must still be in manual mode (indeed, its another timeslot that ended)
            assert cmp_dico(setpoints, {'Dev1':(None,True), 'Dev2':(19.0,False), 'Dev3':(19.0,False)})
            self.devices['Dev2'].scheduled_setpoint = 19.0
            self.devices['Dev3'].scheduled_setpoint = 19.0
            self.step = 14
            # We wait until a timeslot change. The scheduler will detect a change for devices #1 and #2
        elif self.step == 14:
            # Step #14 : Device #1 must go back to scheduled setpoint even if the setpoint is the same
            assert cmp_dico(setpoints, {'Dev1':(16.0,False), 'Dev2':(17.0,False), 'Dev3':(19.0,False)})
            self.step = -1
            scheduler.stop()

        # The steps here after test the manual_mode_reset_event set to 'setpoint_change'
        elif self.step == 21:
            sleep(0.2) # To be sure that the scheduler variable has been set
            # Step #21 : the 3 devices have a scheduled setpoint
            assert cmp_dico(setpoints, {'Dev1':(18.0,False), 'Dev2':(17.0,False), 'Dev3':(20.0,False)})
            self.devices['Dev1'].scheduled_setpoint = 18.0
            self.devices['Dev2'].scheduled_setpoint = 17.0
            self.devices['Dev3'].scheduled_setpoint = 20.0
            self.step = 22

            # Now we put the Dev3 device in manual mode (with a 15° setpoint)
            self.devices['Dev3'].setpoint = 15.0
            scheduler.on_device_setpoint(self.devices['Dev3'])
            # We wait until a timeslot change. The scheduler will detect a change for devices #1 and #2
        elif self.step == 22:
            # Step #12 : Dev3 must be still in manual mode (scheduled setpoint is still 20.0)
            assert cmp_dico(setpoints, {'Dev1':(16.0,False), 'Dev2':(19.0,False), 'Dev3':(None,True)})
            self.devices['Dev1'].scheduled_setpoint = 16.0
            self.devices['Dev2'].scheduled_setpoint = 19.0
            self.step = 23
            # We wait until a timeslot change.
        elif self.step == 23:
            # Step 23 : Dev3 is back on auto mode
            assert cmp_dico(setpoints, {'Dev1':(16.0,False), 'Dev2':(19.0,False), 'Dev3':(19.0,False)})
            self.devices['Dev1'].scheduled_setpoint = 16.0
            self.devices['Dev2'].scheduled_setpoint = 19.0
            self.devices['Dev3'].scheduled_setpoint = 19.0
            self.step = 24

            # Now we put the Dev3 device in manual mode again (with a 15° setpoint)
            self.devices['Dev3'].setpoint = 15.0
            scheduler.on_device_setpoint(self.devices['Dev3'])
            # We wait until a timeslot change.
        elif self.step == 24:
            # Step #24 : Dev3 must be still in manual mode (scheduled setpoint is still 19.0)
            assert cmp_dico(setpoints, {'Dev1':(16.0,False), 'Dev2':(17.0,False), 'Dev3':(None,True)})
            self.step = -1
            scheduler.stop()


    def test_manual_mode_2a(self, caplog):
        self.__manual_mode_2(step=1, manual_mode_reset_event=1, caplog=caplog)

    def test_manual_mode_2b(self, caplog):
        self.__manual_mode_2(step=11, manual_mode_reset_event='timeslot_change', caplog=caplog)

    def test_manual_mode_2c(self, caplog):
        self.__manual_mode_2(step=21, manual_mode_reset_event='setpoint_change', caplog=caplog)

    def __manual_mode_2(self, step, manual_mode_reset_event, caplog):
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

        self.step = step
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
