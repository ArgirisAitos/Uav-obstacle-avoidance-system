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

m.mav.request_data_stream_send(
    m.target_system,
    m.target_component,
    mavutil.mavlink.MAV_DATA_STREAM_ALL,
    4,  # Rate (Hz) 
    1   # Start
)
print("Data Stream Requested (All streams enabled)")

# MQTT 
print("Connecting to MQTT Broker...")
client = mqtt.Client() # Creates the mechanism that handles the communication
client.connect(MQTT_HOST, MQTT_PORT, 60) # Connects to the local IP address
client.loop_start() # Starts running the MQTT in the background
print("MQTT Connected!")

