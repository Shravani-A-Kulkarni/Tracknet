import os
import time
import cv2
import numpy as np
import easyocr
import re
from collections import deque

try:
    from ultralytics import YOLO
except ImportError as e:
    print("❌ ultralytics import error:", e)
    raise

print("🔧 Initializing ADAPTIVE number plate detection module...")

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.abspath(os.path.join(THIS_DIR, "..", "models", "numPbest.pt"))

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"Model file not found at: {MODEL_PATH}")

# Load model
try:
    model = YOLO(MODEL_PATH)
    print("✅ Model loaded")
except Exception as e:
    print("❌ Error loading model:", e)
    raise

# Load OCR
try:
    reader = easyocr.Reader(['en'], gpu=True)
    print("✅ OCR reader loaded")
except Exception as e:
    print("❌ Error loading OCR:", e)
    raise

# Adaptive configurations - will be set per video
ADAPTIVE_CONFIG = {
    'detect_confidence': 0.3,
    'frame_skip': 5,
    'processing_size': 640,
    'ocr_confidence': 0.4,
    'min_plate_width': 50
}

# Indian plate patterns for validation
INDIAN_PLATE_PATTERNS = [
    r'^[A-Z]{2}\d{1,2}[A-Z]{1,2}\d{1,4}$',  # KA01AB1234
    r'^[A-Z]{2}\d{2}[A-Z]{1,2}\d{1,4}$',    # KA01AB1234
    r'^[A-Z]{2}\d{1,2}[A-Z]{2}\d{1,4}$',    # KA01AB1234
    r'^[A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,2}\s?\d{1,4}$',  # With spaces
]

CONFUSION_MAP = {
    'O': '0', 'Q': '0', 'D': '0', 'I': '1', 'L': '1',
    'Z': '2', 'S': '5', 'B': '8', 'G': '6',
    '0': 'O', '1': 'I', '2': 'Z', '5': 'S', '6': 'G', '8': 'B'
}
# Insert this class near the top (after CONFUSION_MAP)

class PlateTracker:
    def __init__(self, max_history=15, conf_threshold=0.7):
        # Stores confirmed plates: {plate_text: deque of (timestamp, confidence)}
        self.confirmed_plates = {} 
        self.max_history = max_history
        self.conf_threshold = conf_threshold
        # Stores recent detections to smooth out flickering
        self.recent_detections = deque(maxlen=3) 

    def update(self, new_detections, frame_number):
        current_plates = {}
        
        # 1. Store recent detections
        self.recent_detections.append(new_detections)
        
        # 2. Accumulate and confirm across recent frames
        plate_counts = {} # {text: count}
        plate_max_conf = {} # {text: max_conf}

        for detections in self.recent_detections:
            for text, conf, _ in detections:
                if text != "Unknown" and conf >= self.conf_threshold:
                    plate_counts[text] = plate_counts.get(text, 0) + 1
                    plate_max_conf[text] = max(plate_max_conf.get(text, 0), conf)
        
        # 3. Final confirmation logic
        confirmed_this_frame = []
        for text, count in plate_counts.items():
            # If seen in at least 2 out of 3 recent frames
            if count >= 2: 
                combined_conf = plate_max_conf[text] # Use max confidence seen recently
                confirmed_this_frame.append((text, combined_conf, None)) # None for bbox
                
                # Update long-term history
                if text not in self.confirmed_plates:
                    self.confirmed_plates[text] = deque(maxlen=self.max_history)
                self.confirmed_plates[text].append((frame_number, combined_conf))

        # Note: Bounding box tracking is complex, we primarily confirm the *text* here.
        # For drawing, we'll use the current frame's box if available.
        return confirmed_this_frame

    def get_confirmed_plates(self):
        return self.confirmed_plates
    

def analyze_video_characteristics(video_path):
    """Analyze video to determine optimal settings"""
    print("🔍 Analyzing video characteristics...")
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return ADAPTIVE_CONFIG
    
    # Sample frames for analysis
    sample_frames = []
    frame_count = 0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    while len(sample_frames) < 10 and frame_count < total_frames:
        ret, frame = cap.read()
        if ret and frame_count % (max(1, total_frames // 10)) == 0:
            sample_frames.append(frame)
        frame_count += 1
    
    cap.release()
    
    if not sample_frames:
        return ADAPTIVE_CONFIG
    
    # Analyze sample frames
    avg_brightness = np.mean([np.mean(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)) for f in sample_frames])
    resolution = sample_frames[0].shape[:2]
    avg_height, avg_width = resolution
    
    print(f"📊 Video Analysis: {avg_width}x{avg_height}, Brightness: {avg_brightness:.1f}")
    
    # Adaptive settings based on analysis
    config = ADAPTIVE_CONFIG.copy()
    
    # Adjust for resolution
    if avg_width > 1920:  # High resolution
        config['processing_size'] = 1280
        config['min_plate_width'] = 80
        config['frame_skip'] = 10  # Skip more frames for high-res
    elif avg_width < 640:  # Low resolution
        config['processing_size'] = 320
        config['min_plate_width'] = 30
        config['frame_skip'] = 3   # Process more frames for low-res
    else:  # Medium resolution
        config['processing_size'] = 640
        config['min_plate_width'] = 50
        config['frame_skip'] = 5
    
    # Adjust for brightness
    if avg_brightness < 50:  # Dark video
        config['detect_confidence'] = 0.2  # Lower threshold for dark videos
        config['ocr_confidence'] = 0.3
    elif avg_brightness > 200:  # Very bright/overexposed
        config['detect_confidence'] = 0.4  # Higher threshold for bright videos
        config['ocr_confidence'] = 0.5
    
    print(f"🎯 Adaptive Settings: Confidence={config['detect_confidence']}, "
          f"FrameSkip={config['frame_skip']}, Size={config['processing_size']}")
    
    return config

def clean_plate_text(text):
    return re.sub(r'[^A-Za-z0-9]', '', (text or "").upper())

def validate_indian_plate(text):
    """Validate if text matches Indian number plate patterns"""
    cleaned = clean_plate_text(text)
    
    if len(cleaned) < 6 or len(cleaned) > 10:
        return False, 0.0
    
    for pattern in INDIAN_PLATE_PATTERNS:
        if re.match(pattern, cleaned):
            if len(cleaned) in [9, 10]:  # Most common lengths
                return True, 0.8
            else:
                return True, 0.6
    
    # Fallback: basic structure check
    if len(cleaned) >= 6 and cleaned[:2].isalpha():
        return True, 0.4
    
    return False, 0.0

def adaptive_preprocess(crop_bgr, is_dark_video=False):
    """Adaptive preprocessing based on video conditions"""
    if crop_bgr.size == 0:
        return []
    
    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    candidates = []
    
    # Technique 1: CLAHE (good for most conditions)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced1 = clahe.apply(gray)
    candidates.append(enhanced1)
    
    # Technique 2: Different approach for dark vs bright videos
    if is_dark_video:
        # For dark videos: increase brightness and contrast
        alpha = 1.5  # Contrast control
        beta = 30    # Brightness control
        enhanced2 = cv2.convertScaleAbs(gray, alpha=alpha, beta=beta)
        candidates.append(enhanced2)
    else:
        # For normal/bright videos: sharpening
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        enhanced2 = cv2.filter2D(gray, -1, kernel)
        candidates.append(enhanced2)
    
    # Resize and convert to BGR for OCR
    results = []
    for cand in candidates:
        h, w = cand.shape
        if h < 20 or w < 60:
            continue
        target_h = max(60, min(120, h))
        scale = target_h / h
        new_w = int(w * scale)
        resized = cv2.resize(cand, (new_w, target_h))
        results.append(cv2.cvtColor(resized, cv2.COLOR_GRAY2BGR))
    
    return results

def adaptive_ocr(crop_bgr, config, is_dark_video=False):
    """Adaptive OCR with multiple attempts"""
    if crop_bgr.size == 0:
        return "Unknown", 0.0
    
    # Get preprocessing variants
    variants = adaptive_preprocess(crop_bgr, is_dark_video)
    if not variants:
        variants = [crop_bgr]  # Fallback to original
    
    best_text, best_conf = "Unknown", 0.0
    
    for variant in variants:
        try:
            rgb = cv2.cvtColor(variant, cv2.COLOR_BGR2RGB)
            results = reader.readtext(
                rgb, 
                detail=1, 
                paragraph=False, 
                allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
                text_threshold=0.3,
                low_text=0.3
            )
        except Exception:
            continue
        
        if not results:
            continue
            
        for res in results[:2]:  # Try top 2 results
            if len(res) >= 3:
                text = clean_plate_text(res[1])
                conf = res[2]
                
                # Validate as Indian plate
                is_valid, pattern_conf = validate_indian_plate(text)
                combined_conf = (conf * 0.7) + (pattern_conf * 0.3)
                
                if is_valid and len(text) >= 6 and combined_conf > best_conf:
                    best_conf = combined_conf
                    best_text = text
    
    if best_text != "Unknown" and best_conf >= config['ocr_confidence']:
        # Apply smart corrections for Indian plates
        corrected = ''.join(CONFUSION_MAP.get(ch, ch) for ch in best_text.upper())
        return corrected, best_conf
    
    return "Unknown", 0.0

def process_frame_adaptive(frame, config):
    """Adaptive frame processing"""
    out_frame = frame.copy()
    
    # Resize for processing
    processing_size = config['processing_size']
    h, w = frame.shape[:2]
    if max(h, w) > processing_size:
        scale = processing_size / max(h, w)
        new_w, new_h = int(w * scale), int(h * scale)
        processing_frame = cv2.resize(frame, (new_w, new_h))
    else:
        processing_frame = frame
    
    # Run detection
    results = model.predict(
        processing_frame, 
        conf=config['detect_confidence'], 
        imgsz=processing_size, 
        verbose=False
    )
    
    recognized = []
    
    for r in results:
        for box in getattr(r, "boxes", []):
            xy = box.xyxy[0].cpu().numpy()
            x1, y1, x2, y2 = map(int, xy)
            conf = float(box.conf.cpu().numpy())
            
            # Adaptive size filtering
            plate_width = x2 - x1
            if plate_width < config['min_plate_width'] or conf < config['detect_confidence']:
                continue
            
            # Map coordinates back to original frame
            scale_x, scale_y = w/processing_frame.shape[1], h/processing_frame.shape[0]
            ox1, oy1 = int(x1 * scale_x), int(y1 * scale_y)
            ox2, oy2 = int(x2 * scale_x), int(y2 * scale_y)
            
            # Crop from original frame for better quality
            crop = frame[oy1:oy2, ox1:ox2]
            if crop.size == 0:
                continue
            
            # Run adaptive OCR
            is_dark = np.mean(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)) < 100
            text, ocr_conf = adaptive_ocr(crop, config, is_dark)
            
            if text != "Unknown":
                recognized.append((text, ocr_conf, (ox1, oy1, ox2, oy2)))
                
                # Draw results
                cv2.rectangle(out_frame, (ox1, oy1), (ox2, oy2), (0, 255, 0), 2)
                label = f"{text} ({ocr_conf:.2f})"
                cv2.putText(out_frame, label, (ox1, max(10, oy1 - 5)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            else:
                # Draw detection without text
                cv2.rectangle(out_frame, (ox1, oy1), (ox2, oy2), (255, 165, 0), 1)
                cv2.putText(out_frame, "Plate", (ox1, max(10, oy1 - 5)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 165, 0), 1)
    
    return out_frame, recognized

def process_video_adaptive(input_path, output_path):
    """Main adaptive video processing function"""
    print(f"\n🎬 ADAPTIVE PROCESSING: {input_path}")
    
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input video not found: {input_path}")
    
    # Analyze video and get adaptive settings
    config = analyze_video_characteristics(input_path)
    
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise Exception(f"Could not open video: {input_path}")
    
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    print(f"📊 Video: {width}x{height}, FPS: {fps}, Frames: {total_frames}")
    plate_tracker = PlateTracker(conf_threshold=config['ocr_confidence'] * 0.9)
    # Output with original resolution
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    frame_count = 0
    processed_count = 0
    detections_count = 0
    start_time = time.time()
    
    print("🚀 Starting adaptive processing...")
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            frame_count += 1
            
            # Adaptive frame skipping
            if frame_count % config['frame_skip'] != 0:
                out.write(frame)
                continue
                
            processed_count += 1
            
            try:
                processed_frame, recognized = process_frame_adaptive(frame, config)
                plate_tracker.update(recognized, frame_count)
                detections_count += len(recognized)
                out.write(processed_frame)
                
            except Exception as e:
                print(f"⚠️ Frame {frame_count} error: {e}")
                out.write(frame)  # Write original frame on error
            
            # Progress updates
            if processed_count % 20 == 0:
                elapsed = time.time() - start_time
                current_fps = processed_count / elapsed if elapsed > 0 else 0
                confirmed_count = len(plate_tracker.get_confirmed_plates())
                print(f"📈 Progress: {frame_count}/{total_frames} | "
                      f"FPS: {current_fps:.1f} | Detections: {detections_count} | Confirmed Unique: {confirmed_count}")
                      
    except Exception as e:
        print(f"❌ Processing error: {e}")
    finally:
        cap.release()
        out.release()
    
    total_time = time.time() - start_time
    print(f"\n✅ ADAPTIVE PROCESSING COMPLETE!")
    print(f"⏱️ Time: {total_time:.1f}s")
    print(f"📊 Frames processed: {processed_count}/{frame_count}")
    print(f"🎯 Total raw detections: {detections_count}")
    print(f"⭐ Total unique confirmed plates: {len(plate_tracker.get_confirmed_plates())}") # NEW line
    print(f"💾 Output: {output_path}")
    print("\nConfirmed Plates:") # NEW
    for text, history in plate_tracker.get_confirmed_plates().items(): # NEW
        avg_conf = np.mean([c for _, c in history]) # NEW
        print(f"  {text} (Seen {len(history)} times, Avg Conf: {avg_conf:.2f})") # NEW
    
    return output_path

# Use this function instead of your current process_video
def process_video(input_path, output_path):
    """Main function to use - handles all videos adaptively"""
    return process_video_adaptive(input_path, output_path)

if __name__ == "__main__":
    print("🧪 Testing adaptive module...")
    test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    config = analyze_video_characteristics("dummy_path")  # Get default config
    processed_frame, recognized = process_frame_adaptive(test_image, config)
    print(f"✅ Adaptive test passed. Detections: {len(recognized)}")