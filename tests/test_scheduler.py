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

# The goal here is to test a realistic schedule
# Steps  1-1x : testing Week A
# Steps 21-2x : testing Week B
# Steps 31-3x : testing schedule inheritance
class TestScheduler_weekA_weekB:
    # SchedulerCallbacks
    def apply_devices_setpoints(self, setpoints: dict[str,tuple[float,bool]]):
        global scheduler
        global expected_setpoints

        if self.step == 1:
            expected_setpoints = {'LivingRoom': (15.0, False), 'Boiler': (16.0, False), 'DiningRoom': (15.0, False), 'Kitchen': (15.0, False), 'MyChild1': (16.5, False),
                                'MyChild2': (18.5, False), 'Parents': (14.0, False), 'Closet': (15.5, False), 'Shower': (18.5, False), 'Office': (15.0, False)}
            assert cmp_dico(setpoints, expected_setpoints)
            self.step = 2
            # going to next time slot
            scheduler.set_test_date(datetime.datetime.fromisoformat("2025-01-20T00:20:00"))
            # We wait until the timeslot change is detected by the scheduler
        
        elif self.step == 2:
            # only 'Shower' must change
            expected_setpoints['Shower'] = (14.0, False)
            assert cmp_dico(setpoints, expected_setpoints)
            self.step = 3
            # Going to next time slot
            scheduler.set_test_date(datetime.datetime.fromisoformat("2025-01-20T06:20:00"))
            # We wait until the timeslot change is detected by the scheduler

        elif self.step == 3:
            # 'WakingUp' temperature set
            expected_setpoints = {'LivingRoom': (15.0, False), 'Boiler': (17.5, False), 'DiningRoom': (16.5, False), 'Kitchen': (16.5, False), 'MyChild1': (16.5, False),
                                'MyChild2': (19.0, False), 'Parents': (16.0, False), 'Closet': (17.5, False), 'Shower': (14.0, False), 'Office': (15.0, False)}
            assert cmp_dico(setpoints, expected_setpoints)
            self.step = 4
            # Going to next time slot
            scheduler.set_test_date(datetime.datetime.fromisoformat("2025-01-20T06:30:00"))
            # We wait until the timeslot change is detected by the scheduler
        
        elif self.step == 4:
            # only 'Shower' must change
            expected_setpoints['Shower'] = (18.5, False)
            assert cmp_dico(setpoints, expected_setpoints)
            self.step = 5
            # Going to next time slot
            scheduler.set_test_date(datetime.datetime.fromisoformat("2025-01-20T07:00:00"))
            # We wait until the timeslot change is detected by the scheduler

        elif self.step == 5:
            # 'DayTime/NotPresent' temperature set
            expected_setpoints = {'LivingRoom': (15.0, False), 'Boiler': (15.5, False), 'DiningRoom': (15.0, False), 'Kitchen': (15.0, False), 'MyChild1': (14.5, False),
                                'MyChild2': (16.0, False), 'Parents': (14.0, False), 'Closet': (16.0, False), 'Shower': (18.5, False), 'Office': (15.0, False)}
            assert cmp_dico(setpoints, expected_setpoints)
            self.step = 6
            # Going to next time slot
            scheduler.set_test_date(datetime.datetime.fromisoformat("2025-01-20T08:00:00"))
            # We wait until the timeslot change is detected by the scheduler

        elif self.step == 6:
            # only 'Shower' must change
            expected_setpoints['Shower'] = (15.0, False)
            assert cmp_dico(setpoints, expected_setpoints)
            self.step = 7
            # Going to next time slot
            scheduler.set_test_date(datetime.datetime.fromisoformat("2025-01-20T14:20:00"))
            # We wait until the timeslot change is detected by the scheduler

        elif self.step == 7:
            # 'DayTime/Present' temperature set
            expected_setpoints['Boiler'] = (17.5, False)
            expected_setpoints['MyChild1'] = (16.5, False)
            expected_setpoints['LivingRoom'] = (17.0, False)
            expected_setpoints['Kitchen'] = (17.0, False)
            expected_setpoints['DiningRoom'] = (17.0, False)
            assert cmp_dico(setpoints, expected_setpoints)
            self.step = 8
            # Going to next time slot
            scheduler.set_test_date(datetime.datetime.fromisoformat("2025-01-20T17:30:00"))
            # We wait until the timeslot change is detected by the scheduler

        elif self.step == 8:
            # 'Evening' temperature set
            expected_setpoints = {'LivingRoom': (18.0, False), 'Boiler': (17.5, False), 'DiningRoom': (16.5, False), 'Kitchen': (16.5, False), 'MyChild1': (17.0, False),
                                'MyChild2': (20.0, False), 'Parents': (16.0, False), 'Closet': (17.5, False), 'Shower': (15.0, False), 'Office': (15.0, False)}
            assert cmp_dico(setpoints, expected_setpoints)
            self.step = 9
            # Going to next time slot
            scheduler.set_test_date(datetime.datetime.fromisoformat("2025-01-20T18:20:00"))
            # We wait until the timeslot change is detected by the scheduler
        
        elif self.step == 9:
            # only 'Shower' must change
            expected_setpoints['Shower'] = (18.5, False)
            assert cmp_dico(setpoints, expected_setpoints)
            self.step = 10
            # Going to next time slot
            scheduler.set_test_date(datetime.datetime.fromisoformat("2025-01-20T21:30:00"))
            # We wait until the timeslot change is detected by the scheduler
        
        elif self.step == 10:
            # 'Night' temperature set
            expected_setpoints = {'LivingRoom': (15.0, False), 'Boiler': (16.0, False), 'DiningRoom': (15.0, False), 'Kitchen': (15.0, False), 'MyChild1': (16.5, False),
                                'MyChild2': (18.5, False), 'Parents': (14.0, False), 'Closet': (15.5, False), 'Shower': (18.5, False), 'Office': (15.0, False)}
            assert cmp_dico(setpoints, expected_setpoints)
            self.step = -1
            scheduler.stop()

        elif self.step == 21:
            # 'DayTime/NotPresent' temperature set
            # => In Week A, the change does not occur at 14:20 but at 16:50 
            expected_setpoints = {'LivingRoom': (15.0, False), 'Boiler': (15.5, False), 'DiningRoom': (15.0, False), 'Kitchen': (15.0, False), 'MyChild1': (14.5, False),
                                'MyChild2': (16.0, False), 'Parents': (14.0, False), 'Closet': (16.0, False), 'Shower': (15.0, False), 'Office': (15.0, False)}
            assert cmp_dico(setpoints, expected_setpoints)
            self.step = 22
            # Going to next time slot
            scheduler.set_test_date(datetime.datetime.fromisoformat("2025-01-20T16:50:00"))
            # We wait until the timeslot change is detected by the scheduler

        elif self.step == 22:
            # 'DayTime/Present' temperature set
            expected_setpoints['Boiler'] = (17.5, False)
            expected_setpoints['MyChild1'] = (16.5, False)
            expected_setpoints['LivingRoom'] = (17.0, False)
            expected_setpoints['Kitchen'] = (17.0, False)
            expected_setpoints['DiningRoom'] = (17.0, False)
            assert cmp_dico(setpoints, expected_setpoints)
            self.step = -1
            scheduler.stop()

        elif self.step == 31:
            # 'WakingUp' temperature set
            expected_setpoints = {'LivingRoom': (15.0, False), 'Boiler': (17.5, False), 'DiningRoom': (16.5, False), 'Kitchen': (16.5, False), 'MyChild1': (16.5, False),
                                'MyChild2': (19.0, False), 'Parents': (16.0, False), 'Closet': (17.5, False), 'Shower': (14.0, False), 'Office': (15.0, False)}
            assert cmp_dico(setpoints, expected_setpoints)
            self.step = 32
            # Going to next time slot
            scheduler.set_test_date(datetime.datetime.fromisoformat("2025-01-20T06:30:00"))
            # We wait until the timeslot change is detected by the scheduler

        elif self.step == 32:
            # only 'Shower' must change
            expected_setpoints['Shower'] = (18.5, False)
            assert cmp_dico(setpoints, expected_setpoints)
            self.step = 33
            # Going to next time slot
            scheduler.set_test_date(datetime.datetime.fromisoformat("2025-01-20T07:00:00"))
            # We wait until the timeslot change is detected by the scheduler

        elif self.step == 33:
            # 'DayTime/Present' temperature set for boiler and living room and 'DayTime/Comfort' for office
            expected_setpoints = {'LivingRoom': (17.0, False), 'Boiler': (17.5, False), 'DiningRoom': (15.0, False), 'Kitchen': (15.0, False), 'MyChild1': (14.5, False),
                                'MyChild2': (16.0, False), 'Parents': (14.0, False), 'Closet': (16.0, False), 'Shower': (18.5, False), 'Office': (17.0, False)}
            assert cmp_dico(setpoints, expected_setpoints)
            self.step = 34
            # Going to next time slot
            scheduler.set_test_date(datetime.datetime.fromisoformat("2025-01-20T14:20:00"))
            # We wait until the timeslot change is detected by the scheduler

        elif self.step == 34:
            # 'DayTime/Present' temperature set
            expected_setpoints['Shower'] = (15.0, False)
            expected_setpoints['MyChild1'] = (16.5, False)
            expected_setpoints['Kitchen'] = (17.0, False)
            expected_setpoints['DiningRoom'] = (17.0, False)
            assert cmp_dico(setpoints, expected_setpoints)
            self.step = 35
            # Going to next time slot
            scheduler.set_test_date(datetime.datetime.fromisoformat("2025-01-20T17:30:00"))
            # We wait until the timeslot change is detected by the scheduler
        
        elif self.step == 35:
            # 'Evening' temperature set, office still in 'DayTime/Comfort'
            expected_setpoints = {'LivingRoom': (18.0, False), 'Boiler': (17.5, False), 'DiningRoom': (16.5, False), 'Kitchen': (16.5, False), 'MyChild1': (17.0, False),
                                'MyChild2': (20.0, False), 'Parents': (16.0, False), 'Closet': (17.5, False), 'Shower': (15.0, False), 'Office': (17.0, False)}
            assert cmp_dico(setpoints, expected_setpoints)
            self.step = 36
            # Going to next time slot
            scheduler.set_test_date(datetime.datetime.fromisoformat("2025-01-20T17:40:00"))
            # We wait until the timeslot change is detected by the scheduler

        elif self.step == 36:
            # only 'Office' must change
            expected_setpoints['Office'] = (15.0, False)
            assert cmp_dico(setpoints, expected_setpoints)
            self.step = -1
            scheduler.stop()

    def test_scheduler_weekA(self):
        # Week A test
        self.__test_scheduler('Normal', 1, "2025-01-20T00:00:00")

    def test_scheduler_weekB(self):
        # Week B test : we test only the week B specific part
        self.__test_scheduler('Normal', 21, "2025-01-27T14:20:00")

    def test_scheduler_inheritance(self):
        self.__test_scheduler('teleworking', 31, "2025-01-20T06:20:00")

    def __test_scheduler(self, active_schedule:str, step:int, start_date:str):
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
