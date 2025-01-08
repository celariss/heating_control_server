import logging
import pytest

from controller import Controller

config_path = './tests/config'

class TestController:
    def test_init_controller(self, caplog):
        caplog.set_level(logging.ERROR)
        controller = Controller(config_path, 'ctrl_')
        controller.start()
        controller.stop()
        assert len(caplog.records) == 0