## v1.2.0 (2025-01-28) :
- history.txt renamed to CHANGELOG.md
- Added schedule inheritance management : a schedule may now inherits from another schedule
- Changes in configuration file format :
	- format version is now 7
	- added 'parent_schedule' field to scheduler/schedules
	- added new command 'set_schedule_properties' to remote_control/receive_topic
- new format for is_alive command
- mqtt_remote_client : format of incoming commands is now checked to avoid crash in case of malformed messages

## v1.1.0 (2025-01-08) :
- Changes in configuration file format :
	- moved 'manual_mode_reset_event' field to '/Scheduler/settings/' so that any remote client can read its value
	- Added new 'set_scheduler_settings' command in remote_control so that any remote client can change settings
- 'manual_mode_reset_event' setting is now handled by the scheduler
- Added some tests using pytest

## v1.0.0 (2023-12-11) :
- Changes in configuration file format :
	- added "add_device", "delete_device", "set_device_entity" to remote api
	- added "on_entities" notification to remote api

## v0.9.5 (2023-11-23) :
- Changes in configuration file format :
	- added timeslots for odd and even weeks in schedule items
	- added last_updated_subtopic in settings/auto_discovery to avoid the detection of an old device

## V0.9.4 (2023-11-19) :
- Changes in configuration file format and interface API with remote clients :
	- Added is_alive message
	- Added min/max temperatures for each device
- bug fix : error in scheduler after a device name change
- state topics for old devices are now automatically cleaned up
- default configuration updated
- custom integration now appears in home assistant and can be installed/uninstalled/stopped/started from GUI

## V0.9.3 (2023-02-18) :
- New mqtt interface definition for remote app
  -> flutter app version must be >= 0.3.0
- New configuration file format
  -> format version updated to 3
- HA install script improved and fully tested

## V0.9.2 (2023-02-11) :
- Added auto install script (for Home Assistant)

## V0.9.1 (2023-02-08) :
- Added auto discover feature (to automatically add exposed devices into configuration file)
  - Configuration file format has changed ("devices" and "settings" sections)
  - Update of client app is needed to maintain compatibility
- Improvements in configuration file error detection (missing file, parsing error)