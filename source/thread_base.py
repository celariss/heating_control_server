__author__      = "Jérôme Cuq"

import threading
import time


class ThreadBase:
    def __init__(self):
        self.lock: threading.Lock = threading.Lock()
        self.thread: threading.Thread = None
        self.must_stop: bool = False
    
    def start(self, target):
        if not self.thread:
            self.thread: threading.Thread = threading.Thread(target=target)
            self.must_stop = False
            self.thread.start()

    def stop(self):
        if self.thread and self.thread.is_alive():
            self.must_stop = True
            if threading.get_ident() != self.thread.ident:
                self.thread.join()
        self.thread = None

    ### Wait for delay sec (delai is a multiple of 0.2s)
    ### return False if the thread main loop must end
    def wait(self, delay:int):
        count = 0.
        while delay>count:
            if not threading.current_thread().is_alive():
                return False
            with self.lock:
                if self.must_stop:
                    return False
            time.sleep(0.2)
            count = count + 0.2
        return True
    
    def join(self, timeout:float = None):
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout)