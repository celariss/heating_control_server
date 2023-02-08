__author__      = "Jérôme Cuq"

from controller import Controller
import time, os

from errors import CfgError

controller = Controller('.', 'heating_ctrl_')
try:
    controller.start()
except CfgError as exc:
    os._exit(1)
    

while True:
    time.sleep(1)

print("exiting")
