__author__      = "Jérôme Cuq"

import logging
import datetime
import threading
import time
from configuration import Configuration
from device import Device

class SchedulerCallbacks:
    # setpoints :
    #  - Each key is a device name, each value a temperature for setpoint
    #  - a None value means that the device has no scheduled setpoint
    def apply_devices_setpoints(self, setpoints: dict[str,float]):
        pass

class Scheduler:
    def __init__(self, config_scheduler:dict, callbacks:SchedulerCallbacks, devices:list[str], init_delay_sec:int, manual_mode_reset_event:str):
        self.logger = logging.getLogger('hcs.scheduler')
        self.logger.info('Starting scheduler')
        self.config_scheduler = config_scheduler
        self.callbacks = callbacks
        self.devices:dict[str,Device] = devices
        # dict key is device name
        self.current_setpoints: dict[str,tuple[float, datetime.datetime]] = {}
        self.active_schedule_changed = False
        self.init_delay:int = init_delay_sec
        self.manual_mode_reset_event:str = manual_mode_reset_event

        self.active_schedule_thread_lock: threading.Lock = threading.Lock()
        self.active_schedule_thread: threading.Thread = threading.Thread(target=self.__follow_active_schedule_thread)
        self.active_schedule_thread_must_stop: bool = False
        self.active_schedule_thread.start()

    def stop(self):
        self.logger.info('Stopping scheduler')
        self.active_schedule_thread_must_stop = True
        self.active_schedule_thread.join()
        self.logger.info('Scheduler has stopped')

    def set_schedule(self, schedule:dict):
        alias = schedule['alias']
        schedule_idx = self.__get_idx_in_schedules(alias)
        if schedule_idx>-1:
            self.config_scheduler['schedules'][schedule_idx] = schedule
            if alias == self.config_scheduler['active_schedule']:
                self.on_active_schedule_changed()
    
    def __get_idx_in_schedules(self, schedule_alias:str):
        idx = 0
        for schedule in self.config_scheduler['schedules']:
            if schedule['alias'] == schedule_alias: return idx
            idx += 1
        return -1

    def on_active_schedule_changed(self):
        with self.active_schedule_thread_lock:
            # notify the thread that active schedule has changed
            self.active_schedule_changed = True

    def on_devices(self, devices:dict[str,Device], scheduler:dict):
        with self.active_schedule_thread_lock:
            self.devices = devices
            self.config_scheduler = scheduler
            # Update the current setpoints so that the schedule thread
            # does not believe that setpoints have changed
            result = self.get_setpoints(datetime.datetime.now())
            if result[0]:
                self.current_setpoints = result[2]

    def refresh_setpoint(self, device_name:str):
        ### send the current scheduled setpoint to device_name

        if device_name in self.devices and device_name in self.current_setpoints:
            # Update the current setpoints so that the schedule thread
            # does not refresh an other device than device_name
            result = self.get_setpoints(datetime.datetime.now())
            if result[0]:
                self.current_setpoints = result[2]
            # now we remove device_name to force the refresh
            self.current_setpoints.pop(device_name)
            self.active_schedule_changed = True

    def set_scheduler(self, scheduler:dict):
        self.config_scheduler = scheduler
        with self.active_schedule_thread_lock:
            # notify the thread that active schedule may has changed
            self.active_schedule_changed = True

    # Called by the controller when new devices are connected
    # This method must change the setpoint of device present in current schedule
    def on_devices_connect(self, new_visible_devices: list[str]):
        with self.active_schedule_thread_lock:
            new_setpoints: dict[str,float] = {}
            for device_name in new_visible_devices:
                if device_name in self.current_setpoints:
                    new_setpoints[device_name] = self.current_setpoints[device_name][0]
            self.callbacks.apply_devices_setpoints(new_setpoints)

    # get the setpoints of all devices for given date/time
    # return (status, active_schedule_alias, dict of setpoints)
    #         where each setpoint is actually a tuple (setpoint, current_timeslot_start_time)
    # note : in case of no active schedule, the method returns (True, None, {})
    def get_setpoints(self, date_:datetime.datetime) ->tuple[bool, str, dict[str,tuple[float,datetime.datetime]]]:
        if 'active_schedule' in self.config_scheduler:
            active_alias:str = self.config_scheduler['active_schedule']
            if active_alias:
                # We look for all schedules matching active alias
                schedules = []
                if 'schedules' in self.config_scheduler:
                    all_schedules = self.config_scheduler['schedules']
                    for schedule in all_schedules:
                        if schedule['alias'] == active_alias:
                            schedules.append(schedule)
                setpoints = {}
                error = False
                for schedule in schedules:
                    # We look for the time slot that applies to schedule at given time
                    timeslots = Scheduler.__find_timeslots(schedule, date_)
                    if not timeslots:
                        self.logger.error("No time slot with current date (missing weekday ?) declared in schedule '"+active_alias+"'")
                        error = True
                    else:
                        log = ''
                        for timeslot in timeslots:
                            log = log + str(timeslot) + ", "
                        self.logger.debug("schedule '"+active_alias+"' currently uses time slots '"+log)

                        index = 0
                        for schedule_item in schedule['schedule_items']:
                            # get active timeslot for current schedule item
                            timeslot = timeslots[index]
                            temp_set_alias = timeslot['temperature_set']
                            for device_name in schedule_item['devices']:
                                setpoint:float = self.__get_setpoint(schedule, device_name, timeslot)
                                if setpoint != None:
                                    setpoints[device_name] = (setpoint, timeslot['start_time'])
                                #else:
                                #    self.logger.error("device '"+device_name+"' is not declared in temperature set '"+temp_set_alias+"' in schedule '"+schedule['alias']+"'")
                                #    error = True
                            index = index+1
            
                if not error:
                    return (True, active_alias, setpoints)
                else:
                    return (False, active_alias, setpoints)
        return (True, None, {})


    ################################################################################
    # PRIVATE STATIC METHODS
    ################################################################################

    def __get_setpoint_from_tempset(device_name, temp_sets, tempset_alias) -> float:
        for temp_set in temp_sets:
            if temp_set['alias'] == tempset_alias:
                for device_temp in temp_set['devices']:
                    if device_temp['device_name']==device_name:
                        # found !
                        return device_temp['setpoint']
                # device not found in this temperature set
                # we need to test the set that this set inherits from
                if ('inherits' in temp_set) and temp_set['inherits']:
                    res:float = Scheduler.__get_setpoint_from_tempset(device_name, temp_sets, temp_set['inherits'])
                    if res: return res
        return None

    # return None if no time slot applies to the given date for one or more devices in schedule
    def __find_timeslots(schedule, date_:datetime.datetime) -> list[dict]:
        result:list[dict] = []
        for schedule_item in schedule['schedule_items']:
            timeslots_sets = schedule_item['timeslots_sets']
            timeslot = Scheduler.__find_timeslot(timeslots_sets, date_)
            if timeslot:
                result.append(timeslot)
            else:
                return None
        return result

    # return None if no time slot applies to the given date
    def __find_timeslot(timeslots_sets, date_:datetime.datetime) -> dict:
        start_time = None
        end_time = None
        found = None
        for timeslots_set in timeslots_sets:
            dates = timeslots_set['dates']
            # Verifying if the given date match the dates in this timeslots_set
            date_ok = False
            target_weekday = str(date_.weekday()+1)
            for d in dates:
                if d==target_weekday:
                    date_ok = True
                    break
            if date_ok:
                # if a week filter (A/B) has been set, we need to check the target week of <date_>
                week_key = 'timeslots'
                if 'timeslots_A' in timeslots_set:
                    week_key = 'timeslots_A' if (int(date_.strftime("%V"))%2==0) else 'timeslots_B'
                timeslots = timeslots_set[week_key]
                timeslot = None
                target_time = date_.time()
                for new_timeslot in timeslots:
                    if not start_time:
                        start_time = new_timeslot['start_time']
                    else:
                        end_time = new_timeslot['start_time']
                        if target_time < end_time:
                            # We have our timeslot
                            found = timeslot
                            break
                    timeslot = new_timeslot

                if (not found):
                    found = timeslots[len(timeslots)-1]
                return found

        return None

    def __get_setpoints_diff(sp1:dict[str,tuple[float,datetime.datetime]], 
                             sp2:dict[str,tuple[float,datetime.datetime]]) -> dict[str,tuple[float,str]]:
        """find all differencies between the 2 given setpoints dictionaries

        :param sp1: first setpoints dictionary
        :type sp1: dict[str,tuple[float,datetime.datetime]]
        :param sp2: second setpoints dictionary
        :type sp2: dict[str,tuple[float,datetime.datetime]]
        :return: each difference is a tuple (setpoint, diff_type), with diff_type in ['-', '+', 'setpoint','timeslot']
        :rtype: dict[str,tuple[float,str]]
        """
        result:dict[str,tuple[float,datetime.datetime,str]] = {}
        for devname in sp1:
            if not devname in sp2:
                result[devname] = (sp1[devname][0], '-')
            else:
                diff_setpoint:bool = sp1[devname][0] != sp2[devname][0]
                diff_timeslot:bool = sp1[devname][1] != sp2[devname][1]
                if diff_setpoint:
                    result[devname] = (sp2[devname][0], 'setpoint')
                elif diff_timeslot:
                    result[devname] = (sp2[devname][0], 'timeslot')
        for devname in sp2:
            if not devname in sp1:
                result[devname] = (sp2[devname][0], '+')
        return result


    ################################################################################
    # PRIVATE METHODS
    ################################################################################

    def __get_setpoint(self, schedule, device_name, timeslot) -> float:
        temp_sets = []
        if 'temperature_sets' in schedule:
            temp_sets = schedule['temperature_sets']
        if 'temperature_sets' in self.config_scheduler:
            temp_sets.extend(self.config_scheduler['temperature_sets'])

        # We must get the setpoint for this device in temperature sets
        temp_set_alias = timeslot['temperature_set']
        return Scheduler.__get_setpoint_from_tempset(device_name, temp_sets, temp_set_alias)

    # Thread that trigger the change of devices setpoint
    def __follow_active_schedule_thread(self):
        with self.active_schedule_thread_lock:
            self.current_setpoints = {}

        time.sleep(self.init_delay)

        while threading.currentThread().is_alive():
            result = self.get_setpoints(datetime.datetime.now())
            if result[0]:
                with self.active_schedule_thread_lock:
                    diff = Scheduler.__get_setpoints_diff(self.current_setpoints, result[2])
                    if len(diff)>0:
                        self.current_setpoints = result[2]
                        self.logger.debug("New setpoints to apply for schedule '"+str(result[1])+"': "+str(self.current_setpoints))
                        # We need to add devices that are not in schedule with a None setpoint
                        #all_setpoints:dict = self.current_setpoints.copy()
                        all_setpoints:dict = {}
                        for devname in self.current_setpoints:
                            item = self.current_setpoints[devname]
                            all_setpoints[devname] = item[0]
                        for device in self.devices:
                            if not device in all_setpoints:
                                all_setpoints[device] = None
                        self.callbacks.apply_devices_setpoints(all_setpoints)

            # Waiting next minute 
            current_minutes = datetime.datetime.now().time().minute
            wait_minutes = (current_minutes+1) % 60
            while wait_minutes>current_minutes:
                time.sleep(2)
                with self.active_schedule_thread_lock:
                    if self.active_schedule_thread_must_stop:
                        # End current thread
                        return
                    # let's see if current shedule has changed
                    if self.active_schedule_changed:
                        self.active_schedule_changed = False
                        current_minutes = wait_minutes
                    else:
                        current_minutes = datetime.datetime.now().time().minute

        