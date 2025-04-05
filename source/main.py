__author__      = "Jérôme Cuq"

from controller import Controller
import time, os
import threading

from errors import CfgError

controller = Controller('.', 'heating_ctrl_')
try:
    controller.start()
except CfgError as exc:
    os._exit(1)
    

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt as exc:
    controller.stop()

print("exiting")