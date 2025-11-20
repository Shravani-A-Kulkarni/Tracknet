import os
import time
import cv2
import numpy as np
import math
import base64
from collections import deque

SPEED_ALERT_HISTORY = deque(maxlen=20)
LAST_SPEED_ALERT_TIME = 0
SPEED_ALERT_COOLDOWN = 3  # seconds between alerts
SPEED_LIMIT = 50 #km/h

try:
    from ultralytics import YOLO
except ImportError as e:
    print("❌ ultralytics import error:", e)
    raise

print("🔧 Initializing speed estimation module...")

# Model path configuration
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.abspath(os.path.join(THIS_DIR, "..", "models", "SEbest.pt"))

print(f"🔍 Model path: {MODEL_PATH}")
print(f"📁 Model exists: {os.path.exists(MODEL_PATH)}")

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"Speed estimation model file not found at: {MODEL_PATH}")

# Load model
try:
    t0 = time.time()
    model = YOLO(MODEL_PATH)
    print(f"✅ Speed Estimation Model loaded in {time.time() - t0:.2f}s")
    if hasattr(model, "names"):
        print("📊 Speed Estimation Model classes:", model.names)
except Exception as e:
    print("❌ Error loading speed estimation model:", e)
    raise

# Speed estimation parameters
class SpeedEstimator:
    def __init__(self):
        self.previous_positions = {}
        self.speeds = {}
        self.frame_count = 0
        self.fps = 30  # Will be updated from video
        self.distance_threshold = 50  # pixels
        self.speed_scale = 0.01  # Scale factor to convert pixels/frame to km/h
        self.alert_history = deque(maxlen=10)
        self.last_alert_time = 0

    def calculate_speed(self, object_id, current_position, current_time):
        
        if object_id in self.previous_positions:
            prev_pos, prev_time = self.previous_positions[object_id]
            
            # Calculate distance moved (in pixels)
            distance = math.sqrt((current_position[0] - prev_pos[0])**2 + 
                            (current_position[1] - prev_pos[1])**2)
            
            # Calculate time difference
            time_diff = current_time - prev_time
            
            if time_diff > 0:
                # Speed in pixels per second
                speed_pixels_per_second = distance / time_diff
                
                # REALISTIC CONVERSION: 1 pixel = ~0.05 meters for 1080p video
                speed_mps = speed_pixels_per_second * 0.05  # meters per second
                speed_kmh = speed_mps * 3.6  # km/h
                
                # ENFORCE REALISTIC LIMITS: No vehicle can go over 300 km/h
                if speed_kmh > 300:
                    return 0  # Ignore unrealistic speeds (tracking error)
                
                return speed_kmh
        
        return 0
    
    def update_positions(self, detections, current_time):
        """
        Update object positions and calculate speeds.
        """
        current_speeds = {}
        
        for i, (x1, y1, x2, y2, obj_id) in enumerate(detections):
            # Calculate center of bounding box
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            current_position = (center_x, center_y)
            
            # Calculate speed
            speed = self.calculate_speed(obj_id, current_position, current_time)
            current_speeds[obj_id] = speed
            
            # Update previous position
            self.previous_positions[obj_id] = (current_position, current_time)
        
        return current_speeds
    
    def cleanup_old_objects(self, current_time, max_age=2.0):
        """
        Remove objects that haven't been detected for a while.
        """
        objects_to_remove = []
        for obj_id, (_, last_time) in self.previous_positions.items():
            if current_time - last_time > max_age:
                objects_to_remove.append(obj_id)
        
        for obj_id in objects_to_remove:
            if obj_id in self.previous_positions:
                del self.previous_positions[obj_id]
            if obj_id in self.speeds:
                del self.speeds[obj_id]

    def check_speed_alert(self, frame, object_id, speed, bbox, frame_count):
        """Check if speed exceeds limit and generate alert"""
        global LAST_SPEED_ALERT_TIME, SPEED_ALERT_HISTORY
        
        if speed > SPEED_LIMIT:
            current_time = time.time()
            
            # Avoid duplicate alerts within cooldown period
            if current_time - LAST_SPEED_ALERT_TIME < SPEED_ALERT_COOLDOWN:
                return None
            
            LAST_SPEED_ALERT_TIME = current_time
            
            alert_data = {
                'type': 'speed',
                'message': f'🚨 SPEEDING VEHICLE DETECTED! Speed: {speed:.1f} km/h',
                'speed': speed,
                'speed_limit': SPEED_LIMIT,
                'timestamp': current_time,
                'frame_count': frame_count,
                'bbox': bbox,
                'snapshot': self.frame_to_base64(frame),
                'alert_id': f"speed_alert_{int(current_time * 1000)}"
            }
            
            # Add to history
            SPEED_ALERT_HISTORY.append(alert_data)
            self.alert_history.append(alert_data)
            
            return alert_data
        return None
    
    def frame_to_base64(self, frame):
        """Convert frame to base64 for web display"""
        try:
            # Resize frame to reduce size for web transmission
            small_frame = cv2.resize(frame, (320, 240))
            _, buffer = cv2.imencode('.jpg', small_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            return base64.b64encode(buffer).decode('utf-8')
        except Exception as e:
            print(f"⚠️ Error converting frame to base64: {e}")
            return ""

def safe_get_boxes(results):
    """
    Safely extract bounding boxes from YOLO results.
    Returns: (coordinates, class_ids, confidence_scores)
    """
    if results is None or len(results) == 0:
        return np.zeros((0, 4)), np.array([]), np.array([])
    
    r = results[0]
    try:
        boxes = r.boxes
        if boxes is None:
            return np.zeros((0, 4)), np.array([]), np.array([])
        
        # Get coordinates, class IDs, and confidence scores
        xyxy = boxes.xyxy
        cls = boxes.cls
        conf = boxes.conf
        
        if xyxy is None:
            return np.zeros((0, 4)), np.array([]), np.array([])
        
        # Convert to numpy arrays
        if hasattr(xyxy, "cpu"):
            coords = xyxy.cpu().numpy()
        else:
            coords = np.array(xyxy)
            
        if cls is None:
            cls_ids = np.zeros((coords.shape[0],), dtype=int)
        else:
            if hasattr(cls, "cpu"):
                cls_ids = cls.cpu().numpy().astype(int)
            else:
                cls_ids = np.array(cls).astype(int)
                
        if conf is None:
            conf_scores = np.zeros((coords.shape[0],), dtype=float)
        else:
            if hasattr(conf, "cpu"):
                conf_scores = conf.cpu().numpy().astype(float)
            else:
                conf_scores = np.array(conf).astype(float)
                
        return coords, cls_ids, conf_scores
    except Exception as e:
        print("⚠️ Error in safe_get_boxes:", e)
        return np.zeros((0, 4)), np.array([]), np.array([])

def draw_speed_detections(frame, coords, cls_ids, conf_scores, speeds, model_names, frame_count, speed_estimator):
    
    alerts = []
    
    for i, ((x1, y1, x2, y2), cid, conf) in enumerate(zip(coords, cls_ids, conf_scores)):
        x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])
        label = model_names.get(int(cid), str(cid))
        
        # Generate object ID for tracking
        obj_id = f"{label}_{i}"
        
        # Get speed for this object
        speed = speeds.get(obj_id, 0)
        
        # Custom color for speed estimation (red for fast, green for slow)
        if speed > 50:
            color = (0, 0, 255)  # Red for high speed
        elif speed > 30:
            color = (0, 165, 255)  # Orange for medium speed
        else:
            color = (0, 255, 0)  # Green for low speed
        
        # Draw bounding box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        
        # Create label with speed information
        label_text = f"{label} {speed:.1f} km/h"
        
        # Draw label with background
        (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        
        # Ensure label doesn't go off the top of the frame
        label_y = max(y1 - 10, th + 10)
        
        # Draw background for text
        cv2.rectangle(frame, (x1, label_y - th - 8), (x1 + tw + 6, label_y), color, -1)
        
        # Draw text
        cv2.putText(frame, label_text, (x1 + 3, label_y - 5), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)  # White text
        
        # Draw speed indicator
        speed_indicator = f"Speed: {speed:.1f} km/h"
        (sw, sh), _ = cv2.getTextSize(speed_indicator, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.putText(frame, speed_indicator, (x1, y2 + sh + 5), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        
        # Generate alert for speeding vehicles
        if speed > SPEED_LIMIT:
            alert = speed_estimator.check_speed_alert(frame, obj_id, speed, (x1, y1, x2, y2), frame_count)
            if alert:
                alerts.append(alert)
                print(f"🚨 Speed alert: {speed:.1f} km/h")
    
    return frame, alerts


def process_video(input_path, output_path):
    """
    Process video for speed estimation with alerts.
    
    Args:
        input_path: Path to input video
        output_path: Path to save processed video
    
    Returns:
        output_path: Path to the processed video
        alert_history: List of speed alerts generated
    """
    print("\n🎬 STARTING SPEED ESTIMATION WITH ALERTS")
    print("📥 Input video:", input_path)
    print("📤 Output video:", output_path)
    
    # Clear previous alerts
    SPEED_ALERT_HISTORY.clear()
    
    # VERIFICATION
    print(f"🔍 VERIFICATION: Using model at {MODEL_PATH}")
    print(f"🔍 VERIFICATION: Model classes: {model.names}")
    print(f"🔍 VERIFICATION: Speed limit: {SPEED_LIMIT} km/h")
    print(f"🔍 VERIFICATION: This is SPEED ESTIMATION (SEbest.pt)")
    
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input video not found: {input_path}")

    # Open video capture
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise Exception(f"Could not open video: {input_path}")
    print("✅ Video capture opened")

    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print(f"📊 Video properties: FPS={fps:.1f}, Resolution={width}x{height}, Frames={total_frames}")

    # Initialize speed estimator
    speed_estimator = SpeedEstimator()
    speed_estimator.fps = fps

    # Initialize video writer
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    if not out.isOpened():
        cap.release()
        raise Exception(f"Could not create output video: {output_path}")
    print("✅ Video writer created")

    frame_count = 0
    frames_with_detections = 0
    total_detections = 0
    total_alerts = 0
    start_time = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("📹 End of video reached")
                break
                
            frame_count += 1
            current_time = frame_count / fps

            try:
                # Run object detection
                results = model(frame, verbose=False)
                coords, cls_ids, conf_scores = safe_get_boxes(results)

                # Prepare detections for speed estimation
                detections = []
                for i, ((x1, y1, x2, y2), cid, conf) in enumerate(zip(coords, cls_ids, conf_scores)):
                    label = model.names.get(int(cid), str(cid))
                    obj_id = f"{label}_{i}"
                    detections.append((x1, y1, x2, y2, obj_id))

                # Update speeds
                speeds = speed_estimator.update_positions(detections, current_time)
                
                # Clean up old objects
                speed_estimator.cleanup_old_objects(current_time)

                alerts = []
                # Draw detections if any found
                if len(coords) > 0:
                    frames_with_detections += 1
                    total_detections += len(coords)
                    frame, alerts = draw_speed_detections(frame, coords, cls_ids, conf_scores, speeds, model.names, frame_count, speed_estimator)
                    total_alerts += len(alerts)

            except Exception as e:
                print(f"❗ Speed estimation error at frame {frame_count}: {e}")
                # Continue processing without detections

            # Write frame
            out.write(frame)

            # Progress reporting
            if frame_count % 100 == 0:
                elapsed = time.time() - start_time
                fps_actual = frame_count / elapsed if elapsed > 0 else 0
                pct = (frame_count / total_frames * 100) if total_frames else 0
                
                # Calculate average speed of detected objects
                avg_speed = np.mean(list(speeds.values())) if speeds else 0
                max_speed = np.max(list(speeds.values())) if speeds else 0
                
                print(f"📊 Progress: {frame_count}/{total_frames} ({pct:.1f}%) - {fps_actual:.1f} FPS - Alerts: {total_alerts}")
                print(f"  Detections: {total_detections}, Avg Speed: {avg_speed:.1f} km/h, Max Speed: {max_speed:.1f} km/h")

    except Exception as e:
        print(f"❌ Speed estimation processing error: {e}")
        raise
    finally:
        # Clean up resources
        cap.release()
        out.release()
        print("🧹 Released video resources")

    # Print summary
    total_time = time.time() - start_time
    avg_fps = frame_count / total_time if total_time > 0 else 0
    
    print("\n✅ SPEED ESTIMATION WITH ALERTS COMPLETE!")
    print(f"📊 Total frames processed: {frame_count}")
    print(f"🎯 Frames with detections: {frames_with_detections}")
    print(f"🚨 Total speed alerts generated: {len(SPEED_ALERT_HISTORY)}")
    print(f"📈 Total objects tracked: {total_detections}")
    print(f"⏱️ Processing time: {total_time:.2f}s")
    print(f"⚡ Average FPS: {avg_fps:.2f}")
    print(f"💾 Output file: {output_path}")

    return output_path, list(SPEED_ALERT_HISTORY)

# Keep the simple version for backward compatibility
def process_video_simple(input_path, output_path):
    """Simple processing without alert system"""
    return process_video(input_path, output_path)[0]  # Return only output_path

def get_speed_alert_history():
    """Get recent speed alert history for UI"""
    return list(SPEED_ALERT_HISTORY)

def clear_speed_alert_history():
    """Clear speed alert history"""
    global SPEED_ALERT_HISTORY
    SPEED_ALERT_HISTORY.clear()

if __name__ == "__main__":
    print("🧪 Testing speed_estimation module...")
    
    # Test function
    def test_module():
        try:
            # Test with a sample image
            test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            results = model(test_image, verbose=False)
            coords, cls_ids, conf_scores = safe_get_boxes(results)
            print(f"✅ Speed Estimation Module test passed. Detections: {len(coords)}")
            return True
        except Exception as e:
            print(f"❌ Speed Estimation Module test failed: {e}")
            return False
    
    test_module()