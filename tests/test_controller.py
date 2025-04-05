import logging
import pytest
from tests.helpers import *

from controller import Controller

class TestController:
    def test_init_controller(self, caplog):
        caplog.set_level(logging.INFO)
        controller = Controller(config_path, 'ctrl_')
        controller.start()
        controller.stop()
        check_no_error(caplog)