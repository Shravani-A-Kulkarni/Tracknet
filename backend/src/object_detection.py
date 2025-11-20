import os
import time
import cv2
import numpy as np

try:
    from ultralytics import YOLO
except ImportError as e:
    print("❌ ultralytics import error:", e)
    raise

print("🔧 Initializing object detection module...")

# Model path configuration
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.abspath(os.path.join(THIS_DIR, "..", "models", "ODbest.pt"))

print(f"🔍 Model path: {MODEL_PATH}")
print(f"📁 Model exists: {os.path.exists(MODEL_PATH)}")

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"Model file not found at: {MODEL_PATH}")

# Load model
try:
    t0 = time.time()
    model = YOLO(MODEL_PATH)
    print(f"✅ Model loaded in {time.time() - t0:.2f}s")
    if hasattr(model, "names"):
        print("📊 Model classes:", model.names)
except Exception as e:
    print("❌ Error loading model:", e)
    raise

def safe_get_boxes(results):
    """
    Safely extract bounding boxes from YOLO results.
    Returns: (coordinates, class_ids)
    """
    if results is None or len(results) == 0:
        return np.zeros((0, 4)), np.array([])
    
    r = results[0]
    try:
        boxes = r.boxes
        if boxes is None:
            return np.zeros((0, 4)), np.array([])
        
        # Get coordinates and class IDs
        xyxy = boxes.xyxy
        cls = boxes.cls
        
        if xyxy is None:
            return np.zeros((0, 4)), np.array([])
        
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
                
        return coords, cls_ids
    except Exception as e:
        print("⚠️ Error in safe_get_boxes:", e)
        return np.zeros((0, 4)), np.array([])

def draw_detections(frame, coords, cls_ids, model_names, color=(0, 255, 0)):
    """
    Draw bounding boxes and labels on frame.
    """
    for (x1, y1, x2, y2), cid in zip(coords, cls_ids):
        x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])
        label = model_names.get(int(cid), str(cid))
        
        # Draw bounding box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        
        # Draw label background
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
        cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 6, y1), color, -1)
        
        # Draw label text
        cv2.putText(frame, label, (x1 + 3, y1 - 5), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)

def process_video(input_path, output_path):
    """
    Process video for object detection.
    
    Args:
        input_path: Path to input video
        output_path: Path to save processed video
    
    Returns:
        output_path: Path to the processed video
    """
    print("\n🎬 STARTING VIDEO PROCESSING")
    print("📥 Input video:", input_path)
    print("📤 Output video:", output_path)
    
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

    # Initialize video writer
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    if not out.isOpened():
        cap.release()
        raise Exception(f"Could not create output video: {output_path}")
    print("✅ Video writer created")

    frame_count = 0
    frames_with_detections = 0
    start_time = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("📹 End of video reached")
                break
                
            frame_count += 1

            try:
                # Run object detection
                results = model(frame, verbose=False)
                coords, cls_ids = safe_get_boxes(results)

                # Draw detections if any found
                if len(coords) > 0:
                    frames_with_detections += 1
                    draw_detections(frame, coords, cls_ids, model.names)

            except Exception as e:
                print(f"❗ Inference error at frame {frame_count}: {e}")
                # Continue processing without detections

            # Write frame
            out.write(frame)

            # Progress reporting
            if frame_count % 100 == 0:
                elapsed = time.time() - start_time
                fps_actual = frame_count / elapsed if elapsed > 0 else 0
                pct = (frame_count / total_frames * 100) if total_frames else 0
                print(f"Progress: {frame_count}/{total_frames} ({pct:.1f}%) - {fps_actual:.1f} FPS")

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
    
    print("\n✅ OBJECT DETECTION COMPLETE!")
    print(f"Total frames processed: {frame_count}")
    print(f"Frames with detections: {frames_with_detections}")
    print(f"Processing time: {total_time:.2f}s")
    print(f"Average FPS: {avg_fps:.2f}")
    print(f"Output file: {output_path}")
    print(f"Output size: {os.path.getsize(output_path) / (1024*1024):.2f} MB")

    return output_path

if __name__ == "__main__":
    # Test the module
    print("🧪 Testing object_detection module...")
    
    # Create a test function
    def test_module():
        try:
            # Test with a sample image
            test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            results = model(test_image, verbose=False)
            coords, cls_ids = safe_get_boxes(results)
            print(f"✅ Module test passed. Detections: {len(coords)}")
            return True
        except Exception as e:
            print(f"❌ Module test failed: {e}")
            return False
    
    test_module()