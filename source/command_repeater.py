__author__      = "Jérôme Cuq"

from datetime import datetime, timedelta
import time
import logging
import threading


class PendingCommand:
    def __init__(self, device:str, command:str, callable, args:list):
        #self.cmdId:str = cmdId
        self.device = device
        self.command = command
        self.callable = callable
        self.args:list = args
        self.repeatTime:datetime = datetime.now()

class CommandRepeater:
    def __init__(self, repeatDelay_sec:int):
        self.logger: logging.Logger = logging.getLogger('hcs.repeater')
        self.logger.info('Starting command repeater : repeatDelay = '+str(repeatDelay_sec)+' sec')
        self.commands:dict[str,PendingCommand] = {}
        self.repeatDelay:timedelta = timedelta(seconds=repeatDelay_sec)
        self.repeat_thread_lock: threading.Lock = threading.Lock()
        self.repeat_thread: threading.Thread = threading.Thread(target=self.__repeat_thread)
        self.repeat_thread_must_stop: bool = False
        self.repeat_thread.start()

    def stop(self):
        self.logger.info('Stopping command repeater')
        with self.repeat_thread_lock:
            self.repeat_thread_must_stop = True
        self.repeat_thread.join()
        self.logger.info('Command repeater has stopped')
    
    # Add or replace repeat command
    def addCommand(self, device:str, command:str, callable, *args):
        with self.repeat_thread_lock:
            cmdId:str = CommandRepeater.__get_cmd_id(device,command)
            self.logger.debug("Adding command to repeater : "+cmdId)
            self.commands[cmdId] = PendingCommand(device, command, callable, args)

    def getCommand(self, device:str, command:str) -> PendingCommand:
        with self.repeat_thread_lock:
            cmdId:str = CommandRepeater.__get_cmd_id(device,command)
            if cmdId in self.commands:
                return self.commands[cmdId]
        return None

    def removeCommand(self, device:str, command:str):
        with self.repeat_thread_lock:
            cmdId:str = CommandRepeater.__get_cmd_id(device,command)
            if cmdId in self.commands:
                self.logger.debug("Removing command for repeater : "+cmdId)
                self.commands.pop(cmdId)

    def remove_device_commands(self, devname:str):
        to_delete:list = []
        with self.repeat_thread_lock:
            for cmdId in self.commands:
                if self.commands[cmdId].device == devname:
                    to_delete.append(cmdId)
            for cmdId in to_delete:
                self.logger.debug("Removing command for repeater : "+cmdId)
                self.commands.pop(cmdId)

    def set_device_name(self, old_name:str, new_name:str):
        to_rename:list = []
        with self.repeat_thread_lock:
            for cmdId in self.commands:
                if self.commands[cmdId].device == old_name:
                    to_rename.append(cmdId)
            for cmdId in to_rename:
                self.logger.debug("Renaming command for repeater : "+cmdId)
                cmd = self.commands.pop(cmdId)
                cmd.device = new_name
                new_cmdId:str = CommandRepeater.__get_cmd_id(cmd.device,cmd.command)
                self.commands[new_cmdId] = cmd

    def repeatCommands(self):
        #self.logger.debug("repeatCommands()")        
        repeatList:list[PendingCommand] = []
        with self.repeat_thread_lock:
            now:datetime = datetime.now()
            for cmdId in self.commands:
                cmd:PendingCommand = self.commands[cmdId]
                actualDuration:timedelta = now-cmd.repeatTime
                if actualDuration>=self.repeatDelay:
                    repeatList.append(cmd)

        for cmd in repeatList:
            self.logger.warning("Repeat command after "+str(actualDuration.seconds)+" sec -> device:'"+cmd.device+"', command:'"+cmd.command+"', args:'"+str(cmd.args)+"'")
            try:
                cmd.callable(*cmd.args)
            except Exception as e:
                self.logger.error("Exception during repeat call : "+str(e))
            cmd.repeatTime = datetime.now()

    # Thread that trigger the repeatition of commands after delay
    def __repeat_thread(self):
        self.logger.info('Command repeater thread started')
        while threading.currentThread().is_alive():
            time.sleep(10)
            self.repeatCommands()
            with self.repeat_thread_lock:
                if self.repeat_thread_must_stop:
                    # End current thread
                    break;
        self.logger.info('Command repeater thread ended')

    def __get_cmd_id(device:str, command:str) -> str:
        return command + '-' + device