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
