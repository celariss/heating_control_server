__author__      = "Jérôme Cuq"

from controller import Controller
import time

controller = Controller('.', 'heating_ctrl_')
while True:
    time.sleep(1)

print("exiting")
