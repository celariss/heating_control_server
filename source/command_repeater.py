__author__      = "Jérôme Cuq"

from datetime import datetime, timedelta
import time
import logging
import threading


class PendingCommand:
    def __init__(self, cmdId:str, callable, args:list):
        self.cmdId:str = cmdId
        self.callable = callable
        self.args:list = args
        self.repeatTime:datetime = datetime.now()

class CommandRepeater:
    def __init__(self, repeatDelay_sec:int):
        self.logger: logging.Logger = logging.getLogger('hcs.repeater')
        self.logger.info('Starting command repeater : repeatDelay = '+str(repeatDelay_sec)+' sec')
        self.commands:dict = {}
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
    def addCommand(self, cmdId:str, callable, *args):
        with self.repeat_thread_lock:
            self.logger.debug("Adding command to repeater : "+cmdId)
            self.commands[cmdId] = PendingCommand(cmdId,callable,args)

    def getCommand(self, cmdId:str) -> PendingCommand:
        with self.repeat_thread_lock:
            if cmdId in self.commands:
                return self.commands[cmdId]
        return None

    def removeCommand(self, cmdId):
        with self.repeat_thread_lock:
            if cmdId in self.commands:
                self.logger.debug("Removing command for repeater : "+cmdId)
                self.commands.pop(cmdId)

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
            self.logger.warning("Repeat command after "+str(actualDuration.seconds)+" sec -> id:'"+cmd.cmdId+"', args:'"+str(cmd.args)+"'")
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