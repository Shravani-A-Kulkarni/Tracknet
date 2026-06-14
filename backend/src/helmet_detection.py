import os
import sys
import time
import cv2
import numpy as np
from collections import deque

# Add project root to Python path for imports to work
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

try:
    from ultralytics import YOLO
except ImportError as e:
    print("❌ ultralytics import error:", e)
    raise

print("🔧 Initializing helmet detection module...")

# Model path configuration
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.abspath(os.path.join(THIS_DIR, "..", "models", "best.pt"))

print(f"🔍 Helmet Model path: {MODEL_PATH}")
print(f"📁 Model exists: {os.path.exists(MODEL_PATH)}")

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"Helmet model file not found at: {MODEL_PATH}")

# Load model
try:
    t0 = time.time()
    # FIX: Use task='detect' and add custom architecture fix
    model = YOLO(MODEL_PATH, task='detect')
    print(f"✅ Helmet Model loaded in {time.time() - t0:.2f}s")
    if hasattr(model, "names"):
        print("📊 Helmet Model classes:", model.names)
except Exception as e:
    print("❌ Error loading helmet model:", e)
    
    # Try loading with custom architecture workaround
    print("🔄 Trying workaround for custom architecture...")
    try:
        # Load model without checking architecture
        import torch
        model = torch.load(MODEL_PATH, map_location='cpu')
        
        # Create a simple YOLO wrapper
        from ultralytics import YOLO as YOLOBase
        
        class CustomYOLOWrapper:
            def __init__(self, model_path):
                self.model = YOLOBase(model_path)
                self.names = {0: 'without_helmet', 1: 'with_helmet'}  # Default classes
                
            def __call__(self, frame, verbose=False):
                return self.model(frame, verbose=verbose)
        
        model = CustomYOLOWrapper(MODEL_PATH)
        print("✅ Helmet Model loaded with workaround!")
    except Exception as e2:
        print("❌ Workaround failed:", e2)
        raise

# Global variables for alert management (if you want alerts later)
ALERT_HISTORY = deque(maxlen=20)
LAST_ALERT_TIME = 0
ALERT_COOLDOWN = 3

def safe_get_boxes(results):
    """
    Safely extract bounding boxes from YOLO results for helmet detection.
    """
    if results is None or len(results) == 0:
        return np.zeros((0, 4)), np.array([]), np.array([])
    
    try:
        # Handle both regular YOLO results and our wrapper
        if hasattr(results, 'boxes'):
            r = results
        else:
            r = results[0]
        
        boxes = r.boxes
        if boxes is None:
            return np.zeros((0, 4)), np.array([]), np.array([])
        
        xyxy = boxes.xyxy
        conf = boxes.conf
        cls = boxes.cls
        
        if xyxy is None:
            return np.zeros((0, 4)), np.array([]), np.array([])
        
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

def draw_helmet_detections(frame, coords, cls_ids, conf_scores, model_names, frame_count):
    """
    Draw helmet detections with custom styling.
    Returns: frame, alerts_list
    """
    alerts = []
    
    for (x1, y1, x2, y2), cid, conf in zip(coords, cls_ids, conf_scores):
        x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])
        
        # Get class name
        if hasattr(model_names, 'get'):
            label = model_names.get(int(cid), str(cid))
        else:
            label = str(cid)
        
        # Different colors for with/without helmet
        if 'with' in str(label).lower() or cid == 1:
            color = (0, 255, 0)  # Green for with helmet
            label_text = f"With Helmet: {conf:.2f}"
        else:
            color = (0, 0, 255)  # Red for without helmet
            label_text = f"Without Helmet: {conf:.2f}"
        
        # Draw bounding box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
        
        # Draw label with background
        (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        cv2.rectangle(frame, (x1, y1 - th - 10), (x1 + tw + 10, y1), color, -1)
        cv2.putText(frame, label_text, (x1 + 5, y1 - 5), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
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
    Helmet detection video processing.
    
    Args:
        input_path: Path to input video
        output_path: Path to save processed video
        alert_callback: Optional callback for real-time alerts
    
    Returns:
        output_path: Path to the processed video
        alert_history: List of all alerts generated
    """
    print("\n🎬 STARTING HELMET DETECTION")
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
    total_detections = 0
    start_time = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("📹 End of video reached")
                break
                
            frame_count += 1

            try:
                # Run helmet detection
                results = model(frame, verbose=False)
                coords, cls_ids, conf_scores = safe_get_boxes(results)

                # Draw detections if any found
                if len(coords) > 0:
                    frames_with_detections += 1
                    total_detections += len(coords)
                    
                    frame, _ = draw_helmet_detections(
                        frame, coords, cls_ids, conf_scores, model.names, frame_count
                    )

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
                print(f"📊 Progress: {frame_count}/{total_frames} ({pct:.1f}%) - {fps_actual:.1f} FPS - Detections: {total_detections}")

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
    
    print("\n✅ HELMET DETECTION COMPLETE!")
    print(f"📊 Total frames processed: {frame_count}")
    print(f"🎯 Frames with detections: {frames_with_detections}")
    print(f"🪖 Total helmet detections: {total_detections}")
    print(f"⏱️ Processing time: {total_time:.2f}s")
    print(f"⚡ Average FPS: {avg_fps:.2f}")
    print(f"💾 Output file: {output_path}")

    return output_path, get_alert_history()

# Simple processing without alerts (backward compatibility)
def process_video_simple(input_path, output_path):
    """Simple processing without alert system"""
    return process_video(input_path, output_path)

if __name__ == "__main__":
    print("🧪 Testing helmet_detection module...")
    
    # Test function
    def test_module():
        try:
            # Test with a sample image
            test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            results = model(test_image, verbose=False)
            coords, cls_ids, conf_scores = safe_get_boxes(results)
            print(f"✅ Helmet Module test passed. Detections: {len(coords)}")
            return True
        except Exception as e:
            print(f"❌ Helmet Module test failed: {e}")
            return False
    
    test_module()