__author__      = "Jérôme Cuq"

import copy
import logging
import datetime
from device import Device
from thread_base import ThreadBase

class SchedulerCallbacks:
    # setpoints :
    #  - Each key is a device name, each value a couple (setpoint, isManual) for value
    #  - a (None, False) value means that the device has no scheduled setpoint
    #  - a (None, True) means that the device is in manual mode (out of schedule)
    #  - ALL known devices must have a defined or None setpoint
    def apply_devices_setpoints(self, setpoints: dict[str,tuple[float,bool]]):
        pass

class Scheduler:
    # manual_mode_reset_event : 'timeslot_change', 'setpoint_change' or an int
    def __init__(self,
                 config_scheduler:dict,
                 callbacks:SchedulerCallbacks,
                 devices:dict[str,Device],
                 init_delay_sec:int,
                 manual_mode_reset_event,
                 thread_wait_time:float = None):
        
        self.logger = logging.getLogger('hcs.scheduler')
        self.logger.info('Starting scheduler')
        self.config_scheduler = copy.deepcopy(config_scheduler)
        self.callbacks = callbacks
        self.devices:dict[str,Device] = devices
        # dict key is device name
        self.current_setpoints: dict[str,tuple[float, datetime.datetime]] = {}
        self.active_schedule_changed = False
        self.init_delay:int = init_delay_sec
        self.manual_mode_reset_event = manual_mode_reset_event
        # for testing purpose : a test date replaces the actual date
        self.test_date = None

        # thread_wait_time is used for testing purpose
        self.thread_wait_time = thread_wait_time
        self.active_schedule_thread: ThreadBase = ThreadBase()
        self.active_schedule_thread.start(self.__follow_active_schedule_thread)

    def stop(self):
        self.active_schedule_thread.stop()
        
    def set_schedule(self, schedule:dict):
        alias = schedule['alias']
        schedule_idx = self.__get_idx_in_schedules(alias)
        if schedule_idx>-1:
            self.config_scheduler['schedules'][schedule_idx] = copy.deepcopy(schedule)
            if alias == self.config_scheduler['active_schedule']:
                self.on_active_schedule_changed(alias)

    def set_manual_mode_reset_event(self, manual_mode_reset_event):
        self.manual_mode_reset_event = manual_mode_reset_event
    
    def __get_idx_in_schedules(self, schedule_alias:str):
        idx = 0
        for schedule in self.config_scheduler['schedules']:
            if schedule['alias'] == schedule_alias: return idx
            idx += 1
        return -1

    def on_active_schedule_changed(self, active_schedule):
        self.config_scheduler['active_schedule'] = active_schedule
        # reset manual mode for all devices
        for devname in self.__get_devices_in_manual_mode():
            self.logger.info("Device['"+devname+"'] is going out of manual setpoint mode")
            self.devices[devname].exitManualMode()
        with self.active_schedule_thread.lock:
            # notify the thread that active schedule has changed
            self.active_schedule_changed = True

    def on_devices(self, devices:dict[str,Device], scheduler:dict):
        with self.active_schedule_thread.lock:
            self.devices = devices
            self.config_scheduler = copy.deepcopy(scheduler)
            # Update the current setpoints so that the schedule thread
            # does not believe that setpoints have changed
            result = self.get_setpoints(self.__get_current_date())
            if result[0]:
                self.current_setpoints = result[2]

    def refresh_setpoint(self, device_name:str):
        ### send the current scheduled setpoint to device_name

        if device_name in self.devices and device_name in self.current_setpoints:
            # Update the current setpoints so that the schedule thread
            # does not refresh an other device than device_name
            result = self.get_setpoints(self.__get_current_date())
            if result[0]:
                self.current_setpoints = result[2]
            # now we remove device_name to force the refresh
            self.current_setpoints.pop(device_name)
            self.active_schedule_changed = True

    def set_scheduler(self, scheduler:dict):
        active_changed = self.config_scheduler['active_schedule'] != scheduler['active_schedule']
        self.config_scheduler = copy.deepcopy(scheduler)
        if active_changed:
            self.on_active_schedule_changed(self.config_scheduler['active_schedule'])
        else:
            with self.active_schedule_thread.lock:
                # notify the thread that active schedule content may has changed
                self.active_schedule_changed = True

    # for testing purpose : a test date replaces the actual date
    def set_test_date(self, test_date:datetime = None):
        self.test_date = test_date

    def on_device_setpoint(self, device:Device):
        # manual mode handling
        if device.hasScheduledSetpoint() and device.setpoint != device.scheduled_setpoint:
            self.logger.info("Device['"+device.name+"'] is going to manual setpoint mode")
            device.enterManualMode()

    # Called by the controller when new devices are connected
    # This method must change the setpoint of device present in current schedule
    def on_devices_connect(self, new_visible_devices: list[str]):
        with self.active_schedule_thread.lock:
            new_setpoints: dict[str,float] = {}
            for device_name in new_visible_devices:
                if device_name in self.current_setpoints:
                    new_setpoints[device_name] = self.current_setpoints[device_name][0]
            self.callbacks.apply_devices_setpoints(new_setpoints)

    # get the setpoints of devices for given date/time
    # return (status, active_schedule_alias, dict of [device_name, setpoint)
    #         where each setpoint is actually a tuple (setpoint, current_timeslot_start_time)
    # note : in case of no active schedule, the method returns (True, None, {})
    # note : only devices that have actual setpoints are present in the result
    def get_setpoints(self, date_:datetime.datetime) -> tuple[bool, str, dict[str,tuple[float,datetime.datetime]]]:
        if 'active_schedule' in self.config_scheduler:
            active_alias:str = self.config_scheduler['active_schedule']
            if active_alias:
                # We look for schedule matching active alias and then ass all its inheritance tree
                schedules = []
                schedule:dict = self.__get_schedule(active_alias)
                schedules.append(schedule)
                while 'parent_schedule' in schedule:
                    schedule = schedule['parent_schedule']
                    schedules.append( self.__get_schedule(schedule) )

                # Now we browse the collected schedules to get all setpoints.
                # For each device, we look for the first setpoint in the inheritance tree
                setpoints = {}
                error = False
                for schedule in schedules:
                    alias = schedule['alias']
                    # We look for the time slot that applies to schedule at given time
                    timeslots = Scheduler.__find_timeslots(schedule, date_)
                    if not timeslots:
                        self.logger.error("No time slot with current date (missing weekday ?) declared in schedule '"+alias+"'")
                        error = True
                    else:
                        log = ''
                        for timeslot in timeslots:
                            log = log + str(timeslot) + ", "
                        self.logger.debug("schedule '"+alias+"' currently uses time slots '"+log)

                        index = 0
                        for schedule_item in schedule['schedule_items']:
                            # get active timeslot for current schedule item
                            timeslot = timeslots[index]
                            temp_set_alias = timeslot['temperature_set']
                            for device_name in schedule_item['devices']:
                                setpoint:float = self.__get_setpoint(schedule, device_name, timeslot)
                                if setpoint != None and not device_name in setpoints:
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

    # return a list of timeslots. Each item of the list is the timeslot that applies to the corresponding schedule_item.
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

    # For testing purpose, the current date can be hooked.
    # The Scheduler never gets datetime.now() directly
    def __get_current_date(self):
        if self.test_date:
            return self.test_date
        return datetime.datetime.now()

    def __get_schedule(self, alias:str) -> dict:
        if 'schedules' in self.config_scheduler:
            all_schedules = self.config_scheduler['schedules']
            for schedule in all_schedules:
                if schedule['alias'] == alias:
                    return schedule
        return None
    
    def __get_devices_in_manual_mode(self) -> dict[str, Device]:
        result:dict[str, Device] = {}
        for name in self.devices:
            device = self.devices[name]
            if device.isInManualMode():
                result[name] = device
        return result
    
    def __get_setpoint(self, schedule, device_name, timeslot) -> float:
        temp_sets = []
        if 'temperature_sets' in schedule:
            temp_sets = schedule['temperature_sets']
        if 'temperature_sets' in self.config_scheduler:
            temp_sets.extend(self.config_scheduler['temperature_sets'])

        # We must get the setpoint for this device in temperature sets
        temp_set_alias = timeslot['temperature_set']
        return Scheduler.__get_setpoint_from_tempset(device_name, temp_sets, temp_set_alias)

    # Thread that triggers the change of devices setpoint
    def __follow_active_schedule_thread(self):
        self.logger.info('Scheduler thread started')

        with self.active_schedule_thread.lock:
            self.current_setpoints = {}

        # Waiting as requested by init_delay
        self.logger.info('Scheduler thread pausing for '+str(self.init_delay)+' sec (init delay)')
        isAlive:bool = self.active_schedule_thread.wait(self.init_delay)
        
        result:tuple[bool, str, dict[str,tuple[float,datetime.datetime]]] = None
        while isAlive:
            result = self.get_setpoints(self.__get_current_date())
            new_setpoints: dict[str,tuple[float,datetime.datetime]] = result[2]
            if result[0]:
                all_setpoints:dict = None
                with self.active_schedule_thread.lock:
                    diffs:dict[str,tuple[float,str]] = None
                    bDiff:bool = False
                    diffs = Scheduler.__get_setpoints_diff(self.current_setpoints, result[2])
                    
                    # Handling of devices manual mode
                    devices_in_manual_mode:dict[str, Device] = self.__get_devices_in_manual_mode()
                    manual_time = None
                    if type(self.manual_mode_reset_event) is int:
                        manual_time = datetime.timedelta(hours = self.manual_mode_reset_event)
                    for name in self.devices:
                        if name in devices_in_manual_mode:
                            device = self.devices[name]
                            switch2auto = False
                            # 1) The manual mode reset setting in set to a integer (nb of hours)
                            if type(self.manual_mode_reset_event) is int:
                                if self.__get_current_date()-device.manual_setpoint_date >= manual_time:
                                    switch2auto = True
                            # 2) The manual mode reset setting in set to a 'timeslot_change'
                            elif self.manual_mode_reset_event == 'timeslot_change':
                                if (name in self.current_setpoints) != (name in new_setpoints):
                                    switch2auto = True
                                elif (name in self.current_setpoints) and (name in new_setpoints):
                                    if self.current_setpoints[name][1] != new_setpoints[name][1]:
                                        switch2auto = True
                            # 3) The manual mode reset setting in set to a 'setpoint_change'
                            elif self.manual_mode_reset_event == 'setpoint_change':
                                if (not name in self.current_setpoints) and (name in new_setpoints):
                                    switch2auto = True
                                elif (name in self.current_setpoints) and (name in new_setpoints):
                                    if self.current_setpoints[name][0] != new_setpoints[name][0]:
                                        switch2auto = True
                            # 4) in all cases, if the current setpoint is identical to the scheduled,
                            #    or if the device is not in the current shedule, it can go out of manual mode
                            if (not device.hasScheduledSetpoint()) or (device.scheduled_setpoint == device.setpoint):
                                switch2auto = True
                            if switch2auto:
                                # This device must go back to scheduled setpoint, if any
                                self.logger.info("Device['"+device.name+"'] is going out of manual setpoint mode")
                                device.exitManualMode()
                                bDiff = True
                                devices_in_manual_mode.pop(name)
                            else:
                                # This device must NOT go back to scheduled setpoint
                                if name in diffs: diffs.pop(name)

                    
                    # Something has changed since last call ?
                    if len(diffs)>0 or bDiff:
                        self.current_setpoints = new_setpoints
                        self.logger.debug("New setpoints to apply for schedule '"+str(result[1])+"': "+str(self.current_setpoints))
                        
                        all_setpoints = {}
                        # We must comply to the callbacks.apply_devices_setpoints prototype :
                        #   1) We add devices that have setpoints in current schedule
                        for devname in self.current_setpoints:
                            if not devname in devices_in_manual_mode:
                                item = self.current_setpoints[devname]
                                all_setpoints[devname] = (item[0], False)
                        #   2) We add devices that are in manual mode
                        for devname in devices_in_manual_mode:
                            all_setpoints[devname] = (None, True)
                        #   3) We add devices that are not in schedule with a None setpoint
                        for devname in self.devices:
                            if not devname in all_setpoints:
                                all_setpoints[devname] = (None, False)
                # At last, we can call the callback !
                if all_setpoints:
                    self.callbacks.apply_devices_setpoints(all_setpoints)

            if self.thread_wait_time:
                # Used for testing purpose
                isAlive = self.active_schedule_thread.wait(self.thread_wait_time)
            else:
                # Waiting next minute
                waitNextMinuteDelay:int = 60 - self.__get_current_date().time().second
                delay:int = 0
                while isAlive and waitNextMinuteDelay>delay:
                    isAlive = self.active_schedule_thread.wait(2)
                    delay = delay + 2
                    if isAlive:
                        with self.active_schedule_thread.lock:
                            # let's see if current shedule has changed
                            if self.active_schedule_changed:
                                self.active_schedule_changed = False
                                delay = waitNextMinuteDelay
                            
        self.logger.info('Scheduler thread has stopped')
                    