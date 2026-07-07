from flask import Flask, Response
import cv2
import time
import threading

JPEG_QUALITY = 30
app = Flask(__name__)
annotated_frame = None
frame_lock = threading.Lock() # Lock for protecting shared frame buffer

def update_frame(frame):
    global annotated_frame
    with frame_lock:
        annotated_frame = frame

# Flask Server 
def generate_frames():
    global annotated_frame
    while True:
        # Lock the frame momentarily to safely copy it
        with frame_lock:
            frame = None if annotated_frame is None else annotated_frame.copy()
        if frame is None:
            time.sleep(0.01)
            continue
        # Sets the parameters for JPEG compression
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
        # Encodes the image into JPEG format
        ret, jpeg = cv2.imencode('.jpg', frame, encode_param)
        if not ret: continue
        # Yields the encoded image in the correct byte format for MJPEG video streaming
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')

# Creats the endpoints where the live video can be viewed
@app.route('/video')
def video():
    # Returns the continuous stream of images
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

def start_server():
    # Starts the local server for video streaming 
    app.run(host="0.0.0.0", port=5000, threaded=True, debug=False)