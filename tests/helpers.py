import logging
import os
import pytest


config_path = './tests/config'

def check_no_error(caplog:pytest.LogCaptureFixture):
    assert len(caplog.records) > 0
    for record in caplog.records:
        assert record.levelname != "ERROR"

def find_first_error(caplog:pytest.LogCaptureFixture) -> logging.LogRecord:
    for record in caplog.records:
        if record.levelname == "ERROR":
            return record
        
def remove_file(path: str):
    if os.path.exists(path):
        os.remove(path)