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

last_gps = 0 # Initialize timestamp for the last global posistion
last_bat = 0 # Initialize timestamp for the last battery
last_speed = 0 #

print("Starting Main Loop... Waiting for messages.")

while True: 
    msg = m.recv_match(blocking=False) # Read incoming data 
    if not msg:
        time.sleep(0.01)
        continue # Reset of the loop

    t = time.time()
    msg_type = msg.get_type() # Read the message name
    # Battery (Volt) 
    if msg_type == "SYS_STATUS" and (t - last_bat) > 1.0: 
        voltage = msg.voltage_battery / 1000.0 # Convert battery voltage from millivolts to volts 
        print(f"Battery Voltage: {voltage:.2f} V")
        client.publish(TOPIC_BAT, str(voltage)) # Send voltage to broker
        last_bat = t # Update the battery timestamp

    # GPS & SPEED
    if msg_type == "GLOBAL_POSITION_INT" and (t - last_gps) > 0.2:
        lat = msg.lat / 1e7 # Convert latitude to decimal degrees
        lon = msg.lon / 1e7 # Convert longitude to decimal degrees
        alt = msg.relative_alt / 1000.0  # Relative altitude (m) 
        print(f"GPS: Lat={lat}, Lon={lon}, Alt={alt}m")
        gps_payload = {"lat": lat, "lon": lon, "alt": alt} # Create a JSON with the GPS data
        client.publish(TOPIC_GPS, json.dumps(gps_payload)) # Publish GPS data as JSON
        
        # Ground speed
        vx = msg.vx / 100.0 # Convert X axis velocity from cm/s to m/s
        vy = msg.vy / 100.0 # Convert Y axis velocity from cm/s to m/s
        speed = (vx*vx + vy*vy) ** 0.5 # Calculate total ground speed
        client.publish(TOPIC_SPEED, str(speed)) # Convert calculated speed to string and publish via MQTT
        # Vertical
        vz= -(msg.vz / 100.0) # Convert Z axis velocity to m/s  
        client.publish(TOPIC_VERTICAL, str(vz)) # Convert vertical speed to string and publish via MQTT
        
        # alt
        alt_m= msg.relative_alt / 1000.0 # Convert relative altitude from millimeters to meters
        client.publish(TOPIC_ALT, str(alt_m)) # Convert altitude to string and publish via MQTT
        last_gps = t # Update the last global timestamp
