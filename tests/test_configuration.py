import os
import pytest

from configuration import Configuration
from errors import *

config_path = './tests/config'

class TestConfiguration:
    def test_init_missingfile(self):
        with pytest.raises(CfgError) as excinfo:
            config:Configuration = Configuration('.', '_', auto_save=False)
        assert excinfo.value.id == ECfgError.MISSING_FILE

    def test_init_badfile_syntax(self):
        with pytest.raises(CfgError) as excinfo:
            config:Configuration = Configuration(config_path, 'bad_', auto_save=False)
        assert excinfo.value.id == ECfgError.BAD_FILE_CONTENT

    def test_init_goodfile(self):
        config:Configuration = Configuration(config_path, 'good_', auto_save=False)

    def test_init_minimalfile(self):
        config:Configuration = Configuration(config_path, 'minimal_', auto_save=False)

    def test_init_default_file(self):
        path = config_path + '/configuration.yaml'
        if os.path.exists(path):
            os.remove(path)
        config:Configuration = Configuration(config_path, '')
        assert os.path.exists(path)
        os.remove(path)

    def test_get_scheduler_manual_mode_reset(self):
        config:Configuration = Configuration(config_path, 'good_', auto_save=False)
        assert type(config.get_scheduler_manual_mode_reset_event()) == int
        assert config.get_scheduler_manual_mode_reset_event() == 6

    def test_settings_manualreset1(self, caplog):
        with pytest.raises(CfgError) as excinfo:
            config:Configuration = Configuration(config_path, 'bad_set_ms1_', auto_save=False)
        assert excinfo.value.id == ECfgError.BAD_VALUE
        assert excinfo.value.node_path == "/scheduler.settings.manual_mode_reset_event"
        assert 'value' in excinfo.value.params and excinfo.value.params['value']=="test_value"
        for record in caplog.records:
            assert record.levelname == "ERROR"
        assert "scheduler.settings.manual_mode_reset_event" in caplog.text
        assert "test_value" in caplog.text

    def test_settings_manualreset2(self, caplog):
        with pytest.raises(CfgError) as excinfo:
            config:Configuration = Configuration(config_path, 'bad_set_ms2_', auto_save=False)
        assert excinfo.value.id == ECfgError.BAD_VALUE
        assert excinfo.value.node_path == "/scheduler.settings.manual_mode_reset_event"
        assert 'value' in excinfo.value.params and excinfo.value.params['value']==25
        for record in caplog.records:
            assert record.levelname == "ERROR"
        assert "scheduler.settings.manual_mode_reset_event" in caplog.text
        assert "25" in caplog.text