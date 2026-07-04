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
        
def yaw_relative(angle_deg, yaw_rate=30):
    # If positive number set direction 1 right else negative -1 for left
    direction = 1 if angle_deg >= 0 else -1
    m.mav.command_long_send(
        m.target_system, # Target drone id
        m.target_component, #Target component id
        mavutil.mavlink.MAV_CMD_CONDITION_YAW, # Sent Yaw command
        0, # Command confirmation set to first attempt
        abs(angle_deg), #Absolute value of degrees
        yaw_rate, # Angular speed
        direction,
        1, # Turn relative to current position
        0, 0, 0 # unused
    )
    time.sleep(abs(angle_deg) / yaw_rate + 0.4) # Wait for turn and extra safety time

def init_params():
    # Setup global flight parameter
    global TRIGGER_DIST, CLEAR_DIST, YAW_SCAN_ANGLE
    global FWD_VEL, FWD_DIST, LATERAL_DIST
    global FWD_TIME, RETREAT_TIME, RESET_TIME, MAX_TRIES
    global RETREAT_DIST, RESET_DIST
    global SLOW_FWD_VEL, SLOW_FWD_DIST, SLOW_LATERAL_DIST

    TRIGGER_DIST = 6.0  # Trigger for obstacle
    CLEAR_DIST   = 9.0  # Clear corridor threshold
    YAW_SCAN_ANGLE = 35 # Scan angle deg

    FWD_VEL      = 1.0 # Velocity
    FWD_DIST     = 5.0 # Avoid distance
    LATERAL_DIST = 3.0 #Paralell move


    FWD_TIME     = FWD_DIST / FWD_VEL # Avoidance flight time
    MAX_TRIES    = 2                  # Max attempts
    RETREAT_DIST = 3.0 # Final back when gave up
    RETREAT_TIME = RETREAT_DIST / FWD_VEL # Reatreat time
    RESET_DIST   = 2.0 # When you try to find a corner again
    RESET_TIME   = RESET_DIST / FWD_VEL # Duration for new distance
    
    # SLOW MODE
    SLOW_FWD_VEL      = FWD_VEL * 0.5 # Reduced velocity
    SLOW_FWD_DIST     = FWD_DIST * 2.0 # Double avoid distance
    SLOW_LATERAL_DIST = LATERAL_DIST * 2.0 # Double parallel move

init_params()
slow_mode = False

# YOLO and CAMERA

STREAM_URL = "tcp://127.0.0.1:8888" # Video stream source address
MODEL_PATH = "yolov8n.pt" # YOLO detection model file
YOLO_IMG_SIZE = 384 # Input image resolution

model = YOLO(MODEL_PATH) # Initialize YOLO model for detection
yolo_lock = threading.Lock() # Lock for thread safe model inference
frame_lock = threading.Lock() # Lock for protecting shared frame buffer
latest_raw_frame = None
is_human_detected = False

# Camera Reader
def camera_reader():
    global latest_raw_frame
    cap = cv2.VideoCapture(STREAM_URL, cv2.CAP_FFMPEG) # Initialize the incoming video stream
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) # Defines the maximum number of frames to be stored in the buffer
    while True:
        success, frame = cap.read() # Capture the next video frame and status
        if not success: # Check if the connection to the camera was lost
            cap.release() # Free the camera resources
            time.sleep(0.5)
            cap = cv2.VideoCapture(STREAM_URL, cv2.CAP_FFMPEG)
            continue
        with frame_lock: # Apply a thread lock to prevent simultaneous read or write access
            latest_raw_frame = frame

# Thread 2: YOLO Processor 
def yolo_processor():
    global latest_raw_frame, is_human_detected
    while True:
        with frame_lock:
         # Check if the camera captured a frame yet
            if latest_raw_frame is None:
                time.sleep(0.01)
                continue
            frame = latest_raw_frame.copy() # Copy to new variable
        with yolo_lock:
            results = model.predict(source=frame, imgsz=YOLO_IMG_SIZE, conf=0.4, classes=[0], verbose=False) # Run YOLO to detect humans
            found = len(results[0].boxes) > 0 # Check if a human is detected in the frame
            temp_annotated = results[0].plot() # Draw the bounding boxes on the image
            
            # sent images in livestreaming
            livestreaming.update_frame(temp_annotated)

        with frame_lock:
            is_human_detected = found
        time.sleep(0.01)