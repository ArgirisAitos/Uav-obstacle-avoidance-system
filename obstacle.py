import time
import struct
import serial
from pymavlink import mavutil
import cv2
import threading
from ultralytics import YOLO
import os
import livestreaming 

# LiDAR 
TF_PORT = '/dev/ttyAMA4'
TF_BAUD = 115200
ser = serial.Serial(TF_PORT, TF_BAUD, timeout=0.2)
ser.reset_input_buffer() # Clear buffer

def read_tfmini(max_time=0.3):
    start = time.time() # timer for timeout check
    while time.time() - start < max_time:
        b = ser.read(1)
        if not b: continue
        # Check for valid packet x59
        if b != b'\x59': continue
        b2 = ser.read(1)
        if b2 != b'\x59': continue
        # Read 7 bytes
        payload = ser.read(7)
        if len(payload) != 7: return None
        # Decode data
        dL, dM, sL, sM, tL, tM, checksum = struct.unpack('<BBBBBBB', payload)
        frame = b'\x59\x59' + payload
        if (sum(frame[:8]) & 0xFF) != checksum: return None
        # Union of distance bytes
        dist_cm = (dM << 8) | dL
        # Convert the meters
        return dist_cm / 100.0 
    return None

def avg_distance(samples=7, max_wait=0.6):
    # Initialize list
    vals = []
    t0 = time.time()
    ser.reset_input_buffer()
    time.sleep(0.01)
    while len(vals) < samples and (time.time() - t0) < max_wait:
        r = read_tfmini() # Read sensor measurment
        if r is None: continue
        d = r
        if d == 0.0: d = 12.0 # Reaplace 0 to 12
        vals.append(d) # save valid value
    if not vals: return None # Return None if empty
    return sum(vals) / len(vals) # Calculate and return average

# Pixhawk
 
connection_string = "udpin:127.0.0.1:14550"
print("Connecting to Pixhawk...")
m = mavutil.mavlink_connection(connection_string) # Start connection
m.wait_heartbeat() # Wait for signal
print("Heartbeat from System ID", m.target_system, "Component ID", m.target_component)

def set_mode(mode_name):
    # Convert mode to integer
    mode_id = m.mode_mapping()[mode_name]
    # Send mode change
    m.mav.set_mode_send(
        m.target_system, # Target drone id
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, # Enable custom modes
        mode_id # New flight mode id
    )
    print(f"Change mode to {mode_name}...")
    start = time.time()
    # Loop to confirm change
    while time.time() - start < 5:
    # Wait up to 1 second for a HEARTBEAT message from Pixhawk
        hb = m.recv_match(type='HEARTBEAT', blocking=True, timeout=1)
        if hb:
    # Get HEARTBEAT messages
            current = mavutil.mode_string_v10(hb)
    # Check if mode matches
            if current == mode_name:
                print(f"Mode : {mode_name}")
                return True
    print(f"No change confirmed in {mode_name}")
    return False

def send_body_velocity(vx, vy, vz, duration):
    print(f"Velocity vx={vx:.2f} vy={vy:.2f} vz={vz:.2f} for {duration:.2f}s")
    # Record start time
    start = time.time()
    # Loop until the specifies duration is reached
    while time.time() - start < duration:
        m.mav.set_position_target_local_ned_send(
            0, # time_boot_ms: 0 for instant execution with no delay
            m.target_system, # Target drone id
            m.target_component, # Target componet id
            mavutil.mavlink.MAV_FRAME_BODY_NED, # Movement based on drone nose not compass
            0b0000111111000111, # Bitmask: enable only velocity
            0, 0, 0, # Ignored position values
            vx, vy, vz, # Target velocity
            0, 0, 0, # Ignored acceleration
            0, 0 # Ignored Yaw
        )
        time.sleep(0.1)
