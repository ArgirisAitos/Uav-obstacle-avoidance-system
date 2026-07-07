import time
import json
from pymavlink import mavutil
import paho.mqtt.client as mqtt

# Settings for MQTT
MQTT_HOST = "127.0.0.1" # Defines the local network address of the system
MQTT_PORT = 1883 # Sets the default communication port

# Definition of all the topics used for telemetry transmission
TOPIC_GPS = "drone/gps"
TOPIC_SPEED = "drone/speed"
TOPIC_BAT = "drone/battery"
TOPIC_ALT = "drone/alt"
TOPIC_VERTICAL = "drone/vertical"

# Connect to PIXHAWK 
connection_string = "udpin:127.0.0.1:14551"

print(f"Connecting to Pixhawk")
try:
    m = mavutil.mavlink_connection(connection_string)
    m.wait_heartbeat()
    print("Heartbeat OK")
except Exception as e:
    print(f"Error connecting to Pixhawk: {e}")
    exit(1)
