import os
import time
import cv2
import numpy as np
import base64
from collections import deque

try:
    from ultralytics import YOLO
except ImportError as e:
    print("❌ ultralytics import error:", e)
    raise

print("🔧 Initializing three seater detection module with Alert System...")

# Model path configuration
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.abspath(os.path.join(THIS_DIR, "..", "models", "3Sbest.pt"))

print(f"🔍 3S Model path: {MODEL_PATH}")
print(f"📁 Model exists: {os.path.exists(MODEL_PATH)}")

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"3S model file not found at: {MODEL_PATH}")

# Load model
try:
    t0 = time.time()
    model = YOLO(MODEL_PATH)
    print(f"✅ 3S Model loaded in {time.time() - t0:.2f}s")
    if hasattr(model, "names"):
        print("📊 3S Model classes:", model.names)
except Exception as e:
    print("❌ Error loading 3S model:", e)
    raise

# Global variables for alert management
ALERT_HISTORY = deque(maxlen=20)  # Store last 20 alerts
LAST_ALERT_TIME = 0
ALERT_COOLDOWN = 3  # seconds between alerts to avoid spam

def safe_get_boxes(results):
    """
    Safely extract bounding boxes from YOLO results for three seater detection.
    """
    if results is None or len(results) == 0:
        return np.zeros((0, 4)), np.array([])
    
    r = results[0]
    try:
        boxes = r.boxes
        if boxes is None:
            return np.zeros((0, 4)), np.array([])
        
        xyxy = boxes.xyxy
        conf = boxes.conf
        cls = boxes.cls
        
        if xyxy is None:
            return np.zeros((0, 4)), np.array([])
        
        # Convert to numpy
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
                
        # Get confidence scores
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

def frame_to_base64(frame):
    """Convert frame to base64 for web display"""
    try:
        # Resize frame to reduce size for web transmission
        small_frame = cv2.resize(frame, (320, 240))
        _, buffer = cv2.imencode('.jpg', small_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        return base64.b64encode(buffer).decode('utf-8')
    except Exception as e:
        print(f"⚠️ Error converting frame to base64: {e}")
        return ""

def generate_alert(frame, confidence, bbox, frame_count):
    """Generate alert data for UI notification"""
    global LAST_ALERT_TIME, ALERT_HISTORY
    
    current_time = time.time()
    
    # Avoid duplicate alerts within cooldown period
    if current_time - LAST_ALERT_TIME < ALERT_COOLDOWN:
        return None
    
    LAST_ALERT_TIME = current_time
    
    alert_data = {
        'type': 'triple_seat',
        'message': f'🚨 TRIPLE SEAT DETECTED! Confidence: {confidence:.2f}',
        'confidence': confidence,
        'timestamp': current_time,
        'frame_count': frame_count,
        'bbox': bbox,
        'snapshot': frame_to_base64(frame),
        'alert_id': f"alert_{int(current_time * 1000)}"
    }
    
    # Add to history
    ALERT_HISTORY.append(alert_data)
    
    return alert_data

def draw_three_seater_detections(frame, coords, cls_ids, conf_scores, model_names, frame_count):
    """
    Draw three seater detections with custom styling and generate alerts.
    Returns: frame, alerts_list
    """
    alerts = []
    
    for (x1, y1, x2, y2), cid, conf in zip(coords, cls_ids, conf_scores):
        x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])
        label = model_names.get(int(cid), str(cid))
        
        # Custom color for three seater (red for alert)
        color = (0, 0, 255) if conf > 0.7 else (0, 165, 255)  # Red for high confidence
        
        # Draw bounding box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
        
        # Draw label with background
        label_text = f"{label}: {conf:.2f}"
        (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        cv2.rectangle(frame, (x1, y1 - th - 10), (x1 + tw + 10, y1), color, -1)
        cv2.putText(frame, label_text, (x1 + 5, y1 - 5), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Generate alert for high confidence detections
        if conf > 0.6:  # Only alert for confident detections
            alert = generate_alert(frame, conf, (x1, y1, x2, y2), frame_count)
            if alert:
                alerts.append(alert)
    
    return frame, alerts

def get_alert_history():
    """Get recent alert history for UI"""
    return list(ALERT_HISTORY)

def clear_alert_history():
    """Clear alert history"""
    global ALERT_HISTORY
    ALERT_HISTORY.clear()

def process_video(input_path, output_path, alert_callback=None):
    """
    Enhanced video processing with real-time alerts.
    
    Args:
        input_path: Path to input video
        output_path: Path to save processed video
        alert_callback: Callback function to send alerts to UI in real-time
    
    Returns:
        output_path: Path to the processed video
        alert_history: List of all alerts generated
    """
    print("\n🎬 STARTING THREE SEATER DETECTION WITH ALERTS")
    print("📥 Input video:", input_path)
    print("📤 Output video:", output_path)
    
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input video not found: {input_path}")

    # Clear previous alerts
    clear_alert_history()

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

    # Initialize video writer
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    if not out.isOpened():
        cap.release()
        raise Exception(f"Could not create output video: {output_path}")
    print("✅ Video writer created")

    frame_count = 0
    frames_with_detections = 0
    total_alerts = 0
    start_time = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("📹 End of video reached")
                break
                
            frame_count += 1

            try:
                # Run three seater detection
                results = model(frame, verbose=False)
                coords, cls_ids, conf_scores = safe_get_boxes(results)

                alerts = []
                # Draw detections if any found
                if len(coords) > 0:
                    frames_with_detections += 1
                    frame, alerts = draw_three_seater_detections(
                        frame, coords, cls_ids, conf_scores, model.names, frame_count
                    )
                    
                    # Send alerts via callback if provided
                    if alert_callback and alerts:
                        for alert in alerts:
                            alert_callback(alert)
                            total_alerts += 1
                            print(f"🚨 Alert sent: {alert['message']}")

            except Exception as e:
                print(f"❗ Detection error at frame {frame_count}: {e}")
                # Continue processing without detections

            # Write frame
            out.write(frame)

            # Progress reporting
            if frame_count % 100 == 0:
                elapsed = time.time() - start_time
                fps_actual = frame_count / elapsed if elapsed > 0 else 0
                pct = (frame_count / total_frames * 100) if total_frames else 0
                print(f"📊 Progress: {frame_count}/{total_frames} ({pct:.1f}%) - {fps_actual:.1f} FPS - Alerts: {total_alerts}")

    except Exception as e:
        print(f"❌ Processing error: {e}")
        raise
    finally:
        # Clean up resources
        cap.release()
        out.release()
        print("🧹 Released video resources")

    # Print summary
    total_time = time.time() - start_time
    avg_fps = frame_count / total_time if total_time > 0 else 0
    
    print("\n✅ THREE SEATER DETECTION WITH ALERTS COMPLETE!")
    print(f"📊 Total frames processed: {frame_count}")
    print(f"🎯 Frames with detections: {frames_with_detections}")
    print(f"🚨 Total alerts generated: {total_alerts}")
    print(f"⏱️ Processing time: {total_time:.2f}s")
    print(f"⚡ Average FPS: {avg_fps:.2f}")
    print(f"💾 Output file: {output_path}")

    return output_path, get_alert_history()

# Simple processing without alerts (backward compatibility)
def process_video_simple(input_path, output_path):
    """Simple processing without alert system"""
    return process_video(input_path, output_path)

if __name__ == "__main__":
    print("🧪 Testing three_seater_detection with alert system...")
    
    # Mock alert callback for testing
    def test_alert_callback(alert_data):
        print(f"🔔 TEST ALERT: {alert_data['message']}")
    
    # Test function
    def test_module():
        try:
            # Test with a sample image
            test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            results = model(test_image, verbose=False)
            coords, cls_ids, conf_scores = safe_get_boxes(results)
            print(f"✅ 3S Module test passed. Detections: {len(coords)}")
            return True
        except Exception as e:
            print(f"❌ 3S Module test failed: {e}")
            return False
    
    test_module()