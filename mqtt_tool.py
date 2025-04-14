__author__      = "Jérôme Cuq"

import sys
import argparse
import time
import logging
import json
import random

from source.protocols import mqttclient

removeall:bool = False
collect_file:str = None
data_tree:dict = {}
only_topics:bool = False

def add_element_to_tree(tree:dict, path:list, value=None):
    result:dict = {}
    node:dict = data_tree
    last:str = path.pop()
    for element in path:
        if not element in node:
            node[element] = {}
        node = node[element]
    node[last] = value

def print_tree(tree:dict, level:int=0):
    for element in sorted(tree.keys()):
        for i in range(level):
            print('    ',end='')
        print(element, end='')
        if isinstance(tree[element], dict):
            print()
            print_tree(tree[element], level+1)
        elif tree[element]:
            print(" : "+tree[element])
        else:
            print()

def on_message(client, mqtt_client: mqttclient.MQTTClient, message, tmp=None):
    global removeall
    global collect_file
    global only_topics
    logger.info("Received message " + str(message.payload)
        + " on topic '" + message.topic
        + "' with QoS " + str(message.qos))
    if removeall and message.retain:
        logger.info("Removing message...")
        mqtt_client.publish("", message.topic, retain=True, qos=1)
    if collect_file:
        path = message.topic.split('/')
        value = ''
        if not only_topics: value = message.payload.decode("utf-8")
        add_element_to_tree(data_tree, path, value)
        with open(collect_file, 'w', encoding="utf-8") as config_file:
            json.dump(data_tree, config_file, indent = 4, sort_keys=True, ensure_ascii=False)


def on_connect(client, mqtt_client: mqttclient.MQTTClient, message, returncode):
    global publish_data
    if returncode:
        print("Not connected ! Return Code :" + str(returncode))
    else:
        print("Connected !")
        if subscribe or removeall or collect_file:
            print('Subscribing ...')
            mqtt_client.subscribe(topic,1)
        if publish_data:
            if publish_data == "''":
                publish_data = ''
            print('Publishing ...')
            print('  - topic: '+topic)
            print('  - data : '+ publish_data)
            print('  - retain : '+ str(retain))
            mqtt_client.publish(publish_data, topic, retain=retain, qos=1)
        if collect_file:
            print('Collecting data to file until script is stopped...')

def on_publish(client, mqtt_client: mqttclient.MQTTClient, returncode):
    global EXIT
    if not subscribe:
        EXIT = True

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

mqtt_transport = 'websockets' # or 'tcp'
mqtt_clientid = "pyclient_" + str(random.randint(10000,99999))
topic = '#'
EXIT = False

parser = argparse.ArgumentParser()
parser.add_argument("broker", help='MQTT broker address')
parser.add_argument("port", type=int, help='Broker IP port')
parser.add_argument("user", help='Broker user name')
parser.add_argument("pwd", help='Broker password')
parser.add_argument("topic", help='Topic to publish/subscribe to')
parser.add_argument("-s", "--subscribe", action='store_true', help="Subscribe")
parser.add_argument("-r", "--removeall", action='store_true', help="Remove all published data on topic (data with retain flag)")
parser.add_argument("-p", "--publish", metavar='data', help="Publish data")
parser.add_argument("-c", "--collect", metavar='file', help="Subscribe and save data tree to file")
parser.add_argument("--no_ssl", action='store_true', help="Disable SSL")
parser.add_argument("--retain", action='store_true', help="Set retain flag (on publish)")
parser.add_argument("--only_topics", action='store_true', help="Don't store values (when collecting)")
args = parser.parse_args()

mqtt_broker = args.broker
mqtt_port = args.port
mqtt_user = args.user
mqtt_pwd = args.pwd
ssl = not args.no_ssl
retain = args.retain
topic = args.topic
subscribe = args.subscribe
removeall = args.removeall
publish_data = args.publish
collect_file = args.collect
only_topics = args.only_topics
if not (subscribe or publish_data or removeall or collect_file):
    print('error: either --subscribe or --publish or --removeall or --collect argument is required')
    print()
    parser.print_help()
    parser.exit()

mqtt_client = mqttclient.MQTTClient(mqtt_clientid, mqtt_broker, mqtt_port, mqtt_user, mqtt_pwd, mqtt_transport, ssl=ssl)
mqtt_client.set_callbacks(on_connect=on_connect, on_publish=on_publish, on_message=on_message)
mqtt_client.connect()

while not EXIT:
    time.sleep(1)

if collect_file:
    print_tree(data_tree)