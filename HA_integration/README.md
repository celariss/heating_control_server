# Installation of the Heating Control Server in Home Assistant

##

This readme file is about installing the server in your Home Assistant instance (as a custom integration).

To do it, you need :
- A running instance of Home Assistant
- An access to the HA config folder (it is a folder shared by HA)

## Install the mosquitto MQTT Broker add-on
The server needs a MQTT broker instance to connect to. To activate Mosquitto broker inside HA, do the following :
- Install the mosquitto broker add-on from the add-ons section of HA parameters
- Declare the user 'mqtt' (or any other!) in HA settings and choose his password wisely
> Detailed instructions can be found online...

## Install the add-on using install.py
To install the server as a add-on (custom component) on your Home Assistant instance, the easier way is to use the install script.

#### 1. Install third-party python libraries
```sh
pip install ruamel.yaml
```
> [Ruamel.yaml] is a YAML parser/emitter that supports roundtrip preservation of comments, seq/map flow style, and map key order. It is very useful to patch yaml files without messing with existing structure and comments.

#### 2. Create an install.ini file
Copy the file `install_example.ini` to `install.ini` and update all parameters to match your own configuration :
```ini
[default]
    # Path to shared config folder of Home Assistant.
    # The following example is for Windows, using the IP Address of Home Assistant
    HAConfigFolder = \\192.168.1.150\config\
    
    # IP address or DNS host name of your MQTT broker
    # Since the serveur is colocated with Home Assistant, use 127.0.0.1
    MqttBroker = 127.0.0.1
    
    # MQTT user name and password, as configured in your HA instance
    MqttUser = mqtt
    MqttPwd = mypassword

    # Mqtt websocket unsecured port
    MqttPort = 1884
    
    # Always use false for 127.0.0.1
    MqttSsl = false
```

#### 3. Execute the script
```sh
python install.py -p install.ini
```
If needed, the script may ask you some questions (for example, in case a server version is already present)

> IMPORTANT: Do not forget to restart your Home Assistant instance !

That's it ! Heating controler server is already looking for existing thermostat on your HA instance to make them available on mobile and desktop clients.


## ... Or install manually
The instructions that follow are done by the install script, but you also can execute them by hand :
#### 1. Update the configuration file
The configuration file to update is located here : `./heating_ctrl_default_configuration.yaml`

> **Note :**
> - To understand the meaning of each parameter in the configuration file, read the file `./documented_configuration.yaml`
> - This file will never be overwritten by the server. When the running server change the configuration file content, for example after the reception of a new schedule from the mobile app, it saves the new configuration in an other file named `« heating_ctrl_configuration.yaml »`

You just have to update the MQTT parameters in « protocols/mqtt » section :
  ```yaml
  protocols:
    mqtt:
    - name:   "mqtt_ha"
      user:   "mqtt"             #<-- put your mqtt user name here
      pwd:    "gfkjGHT8sx_"      #<-- put your mqtt password here
      broker: "myha.duckdns.org" #<-- put your HA instance hostname or IP address here
      port:   8884               #<-- put your (websocket) mqtt secure port here
      ssl:    true
  ```

#### 2. Install the add-on
> **Note :**
> - `./HA_integration/configuration.yaml` contains code to make HA publish the states of all thermostats automatically to the MQTT broker
> - `./HA_integration/automations.yaml` contains code to subscribe (on the MQTT broker) to setpoint changes coming from the heating control server

You must have access to the « `config` » shared folder of your HA instance :
1. Add the content of `./HA_integration/configuration.yaml` in HA `config/configuration.yaml`
2. Add the content of `./HA_integration/automations.yaml` in HA `config/automations.yaml`
3. copy `./HA_integration/custom_components/heating_control_srv` folder to HA `config/custom_components/` folder
4. copy `./source` folder to HA `config/custom_components/heating_control_srv/` folder
5. in HA config folder, rename `config/custom_components/heating_control_srv/source` to `config/custom_components/heating_control_srv/heating_control_server`
6. Copy all files from `./HA_integration/custom_components/config/` folder to HA `config/` folder
7. Add `./heating_ctrl_default_configuration.yaml` to HA `config/` folder
8. Edit HA `config/configuration.yaml` file and add the following line :
```yaml
heating_control_srv :
```
9. Restart HA server


[//]: # (These are reference links used in the body of this note and get stripped out when the markdown processor does its job. There is no need to format nicely because it shouldn't be seen. Thanks SO - http://stackoverflow.com/questions/4823468/store-comments-in-markdown-syntax)

  [ruamel.yaml]: <https://pypi.org/project/ruamel.yaml/>
  