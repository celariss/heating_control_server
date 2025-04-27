from time import sleep
import pytest
from tests.helpers import *

from scheduler import Scheduler, SchedulerCallbacks
from configuration import Configuration
from device import Device
import datetime


scheduler: Scheduler = None
expected_setpoints: dict

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

# The goal here is to test inheritance
class TestScheduler_inheritance:
    # SchedulerCallbacks
    def scheduler_error(self):
        assert False

    def apply_devices_setpoints(self, setpoints: dict[str,tuple[float,bool]]):
        global scheduler
        global expected_setpoints

        if self.step == 1:
            expected_setpoints = {'LivingRoom': (15.0, False), 'Boiler': (16.0, False), 'DiningRoom': (15.0, False), 'Kitchen': (15.0, False), 'MyChild1': (16.5, False),
                                'MyChild2': (18.5, False), 'Parents': (14.0, False), 'Closet': (15.5, False), 'Shower': (15.0, False), 'Office': (15.0, False)}
            assert cmp_dico(setpoints, expected_setpoints)
            self.step = 2
            # going to next time slot
            scheduler.set_test_date(datetime.datetime.fromisoformat("2025-04-26T14:20:00"))
            # We wait until the timeslot change is detected by the scheduler

        elif self.step == 2:
            # 'DayTime/NotPresent' temperature set
            expected_setpoints = {'LivingRoom': (17.5, False), 'Boiler': (17.5, False), 'DiningRoom': (17.5, False), 'Kitchen': (17.0, False), 'MyChild1': (17.0, False),
                                'MyChild2': (18.5, False), 'Parents': (16.0, False), 'Closet': (17.5, False), 'Shower': (15.0, False), 'Office': (15.0, False)}
            assert cmp_dico(setpoints, expected_setpoints)
            self.step = -1
            scheduler.stop()

    # here we test if the scheduler gets from "Normal" missing values in "Inherited" 
    def test_scheduler_partial_inheritance(self, caplog):
        # given date is not defined in "Holiday1", so scheduler must get timeslots from parent ("Normal" schedule)
        self.__test_scheduler('Holiday1', 1, "2025-04-26T00:00:00", caplog)

    def __test_scheduler(self, active_schedule:str, step:int, start_date:str, caplog):
        self.devices: dict[str, Device] = {}
        config:Configuration = Configuration(config_path, 'realistic1_')
        config_scheduler = config.get_scheduler()
        config_devices = config.get_devices()

        config_scheduler['active_schedule'] = active_schedule
        
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
                        1,
                        'setpoint_change',
                        0.2)
        
        scheduler.set_test_date(datetime.datetime.fromisoformat(start_date))
        
        scheduler.active_schedule_thread.join()
        scheduler = None
        assert self.step == -1
        check_no_error(caplog, False)