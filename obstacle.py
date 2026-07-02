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