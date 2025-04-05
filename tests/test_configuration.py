import datetime
import os
import pytest
from tests.helpers import *

from configuration import Configuration
from errors import *


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

    def test_schedule_parent(self):
        # Preparing a configuration to test 'parent' management
        config:Configuration = Configuration(config_path, 'minimal_', auto_save=False)
        config_scheduler = config.get_scheduler()
        excinfo = config.add_device('Dev1', '', '', {})
        assert not excinfo
        excinfo = config.set_temperature_sets([{'alias': 'TSet1', 'devices':[{'device_name':'Dev1','setpoint':10.0}]}])
        assert not excinfo
        items = [{'devices':['Dev1'],
                  'timeslots_sets':[{'dates':['1','2','3','4','5','6','7'],'timeslots':[
                           {'start_time':datetime.time.fromisoformat('00:00:00'),
                            'temperature_set':'TSet1'}]}]}]
        
        excinfo = config.set_schedule({'alias':'test', 'schedule_items':items, 'parent_schedule':''})
        assert excinfo and excinfo.id == ECfgError.BAD_REFERENCE
        excinfo = config.set_schedule({'alias':'test', 'schedule_items':items, 'parent_schedule':'toto'})
        assert excinfo and excinfo.id == ECfgError.BAD_REFERENCE
        excinfo = config.set_schedule({'alias':'parent', 'schedule_items':items})
        assert not excinfo
        excinfo = config.set_schedule({'alias':'test', 'schedule_items':items, 'parent_schedule':'parent'})
        assert config.get_schedule('test') != None
        # Testing circular reference detection
        excinfo = config.set_schedule({'alias':'test2', 'schedule_items':items, 'parent_schedule':'test'})
        assert not excinfo
        excinfo = config.set_schedule({'alias':'parent', 'schedule_items':items, 'parent_schedule':'test2'})
        assert excinfo and excinfo.id == ECfgError.CIRCULAR_REF

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
        assert find_first_error(caplog)
        assert "scheduler.settings.manual_mode_reset_event" in caplog.text
        assert "test_value" in caplog.text

    def test_settings_manualreset2(self, caplog):
        with pytest.raises(CfgError) as excinfo:
            config:Configuration = Configuration(config_path, 'bad_set_ms2_', auto_save=False)
        assert excinfo.value.id == ECfgError.BAD_VALUE
        assert excinfo.value.node_path == "/scheduler.settings.manual_mode_reset_event"
        assert 'value' in excinfo.value.params and excinfo.value.params['value']==25
        assert find_first_error(caplog)
        assert "scheduler.settings.manual_mode_reset_event" in caplog.text
        assert "25" in caplog.text