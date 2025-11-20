import cv2
import numpy as np
import time
import easyocr
import re
from ultralytics import YOLO
import os
import sys
import traceback

class LicensePlateDetector:
    def __init__(self, model_path, conf_threshold=0.5, use_easyocr=True):
        """
        Initialize the license plate detector with OCR
        """
        self.conf_threshold = conf_threshold
        self.use_easyocr = use_easyocr
        
        # Load detection model using Ultralytics YOLO
        try:
            self.model = YOLO(model_path)
            print("YOLO model loaded successfully!")
            
        except Exception as e:
            print(f"Error loading model: {e}")
            raise
        
        # Initialize OCR reader
        if use_easyocr:
            try:
                self.reader = easyocr.Reader(['en'])
                print("EasyOCR initialized for text recognition")
            except Exception as e:
                print(f"Error initializing EasyOCR: {e}")
                self.reader = None
        else:
            self.reader = None
    
    def preprocess_plate_for_ocr(self, plate_image):
        """
        Preprocess license plate image for better OCR results
        """
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(plate_image, cv2.COLOR_BGR2GRAY)
            
            # Apply noise reduction
            denoised = cv2.medianBlur(gray, 3)
            
            # Increase contrast
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            contrast_enhanced = clahe.apply(denoised)
            
            # Apply threshold to get binary image
            _, binary = cv2.threshold(contrast_enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            return binary
        except Exception as e:
            print(f"Plate preprocessing error: {e}")
            return plate_image
    
    def recognize_plate_text(self, plate_image):
        """
        Recognize text from license plate image using OCR
        """
        try:
            if self.reader is None:
                return "OCR not available", 0.0
                
            # Preprocess plate image
            processed_plate = self.preprocess_plate_for_ocr(plate_image)
            
            # Use EasyOCR
            results = self.reader.readtext(processed_plate, detail=1, paragraph=False)
            
            if results:
                # Get the text with highest confidence
                text = ' '.join([result[1] for result in results])
                confidence = np.mean([result[2] for result in results])
                
                # Clean the text (remove special characters, keep alphanumeric and spaces)
                cleaned_text = re.sub(r'[^a-zA-Z0-9\s]', '', text).strip()
                if cleaned_text:
                    return cleaned_text, confidence
                else:
                    return "No valid text", 0.0
            else:
                return "No text", 0.0
                
        except Exception as e:
            print(f"OCR Error: {e}")
            return "OCR Error", 0.0
    
    def detect_and_recognize(self, image):
        """
        Perform license plate detection and text recognition
        """
        try:
            # Run YOLO inference
            results = self.model(image, conf=self.conf_threshold, verbose=False)
            
            detections = []
            
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        # Get bounding box coordinates
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                        conf = box.conf[0].cpu().numpy()
                        cls = box.cls[0].cpu().numpy()
                        
                        det = {
                            'bbox': [x1, y1, x2, y2],
                            'confidence': float(conf),
                            'class': int(cls)
                        }
                        
                        # Extract license plate region
                        plate_region = image[y1:y2, x1:x2]
                        
                        # Only process if plate region is valid
                        if (plate_region.size > 0 and 
                            plate_region.shape[0] > 10 and 
                            plate_region.shape[1] > 10 and
                            plate_region.shape[0] < image.shape[0] and
                            plate_region.shape[1] < image.shape[1]):
                            
                            text, text_confidence = self.recognize_plate_text(plate_region)
                            det['plate_text'] = text
                            det['text_confidence'] = text_confidence
                        else:
                            det['plate_text'] = "Invalid region"
                            det['text_confidence'] = 0.0
                        
                        detections.append(det)
            
            return detections
            
        except Exception as e:
            print(f"Detection error: {e}")
            return []
    
    def process_video(self, video_path, output_path=None, display=True):
        """
        Process video for license plate detection and recognition
        """
        # Check if video file exists
        if not os.path.exists(video_path):
            print(f"Error: Video file '{video_path}' not found!")
            return
        
        # Open video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"Error: Could not open video {video_path}")
            print("Please check if the file is a valid video format")
            return
        
        # Get video properties
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        print(f"Video: {width}x{height}, {fps} FPS, {total_frames} frames")
        
        # Setup video writer if output path is provided
        if output_path:
            # Create output directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        else:
            out = None
        
        # Check if display is possible
        if display:
            try:
                # Test if GUI works
                test_window = np.zeros((100, 100, 3), dtype=np.uint8)
                cv2.imshow('Test', test_window)
                cv2.destroyWindow('Test')
                display_available = True
                print("GUI display is available")
            except:
                display_available = False
                print("GUI display not available - running in headless mode")
        else:
            display_available = False
        
        # Process video
        frame_count = 0
        total_detections = 0
        start_time = time.time()
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Perform detection and recognition
                detections = self.detect_and_recognize(frame)
                
                # Draw detections and text
                for det in detections:
                    x1, y1, x2, y2 = det['bbox']
                    conf = det['confidence']
                    plate_text = det.get('plate_text', 'No text')
                    text_conf = det.get('text_confidence', 0.0)
                    
                    # Draw bounding box
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    
                    # Draw text background
                    text = f"{plate_text} ({text_conf:.2f})"
                    text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                    text_bg_y1 = max(0, y1 - text_size[1] - 10)
                    text_bg_y2 = max(0, y1)
                    cv2.rectangle(frame, (x1, text_bg_y1), (x1 + text_size[0], text_bg_y2), (0, 255, 0), -1)
                    
                    # Draw text
                    cv2.putText(frame, text, (x1, max(15, y1 - 5)), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
                    
                    # Draw detection confidence
                    cv2.putText(frame, f"Det: {conf:.2f}", (x1, min(frame.shape[0] - 10, y2 + 20)), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    
                    total_detections += 1
                
                # Add frame counter
                cv2.putText(frame, f"Frame: {frame_count}/{total_frames}", 
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(frame, f"Detections: {len(detections)}", 
                           (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                # Write frame to output
                if out:
                    out.write(frame)
                
                # Display if available
                if display_available:
                    cv2.imshow('License Plate Detection & Recognition', frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        print("Processing stopped by user")
                        break
                else:
                    # Print progress in console
                    if frame_count % 30 == 0:
                        elapsed = time.time() - start_time
                        fps_processed = frame_count / elapsed if elapsed > 0 else 0
                        print(f"Processing frame {frame_count}/{total_frames} ({fps_processed:.1f} FPS) - Detections: {len(detections)}")
                
                frame_count += 1
                
        except KeyboardInterrupt:
            print("\nProcessing interrupted by user")
        except Exception as e:
            print(f"Error during video processing: {e}")
        
        finally:
            # Cleanup
            cap.release()
            if out:
                out.release()
            if display_available:
                cv2.destroyAllWindows()
            
            # Print summary
            elapsed = time.time() - start_time
            print(f"\nProcessing complete!")
            print(f"Total frames processed: {frame_count}")
            print(f"Total detections: {total_detections}")
            if elapsed > 0:
                print(f"Processing time: {elapsed:.2f} seconds")
                print(f"Average FPS: {frame_count/elapsed:.2f}")
            
            # Save detection log
            self.save_detection_log(frame_count, total_detections, output_path)

    def save_detection_log(self, frames_processed, total_detections, output_path):
        """Save processing summary to a log file"""
        log_content = f"""
License Plate Detection Log
===========================
Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}
Frames Processed: {frames_processed}
Total Detections: {total_detections}
Model: plateSentry.pt
OCR: {'EasyOCR' if self.use_easyocr else 'None'}
        """
        print(log_content)
        
        # Save to file
        log_filename = "detection_log.txt"
        with open(log_filename, 'w') as f:
            f.write(log_content)
        print(f"Log saved to: {log_filename}")

def main():
    # Initialize detector with OCR
    model_path = "plateSentry.pt"
    
    # Check if model exists
    if not os.path.exists(model_path):
        print(f"Error: Model file '{model_path}' not found!")
        print("Please make sure the model file is in the current directory")
        return
    
    try:
        detector = LicensePlateDetector(model_path, conf_threshold=0.5, use_easyocr=True)
        
        # Test on video - you can change this path
        video_path = "car.mp4"  # Update with your video path
        
        if not os.path.exists(video_path):
            print(f"Video file '{video_path}' not found!")
            print("Please update the video_path variable with your video file path")
            return
        
        output_path = "output_with_text.mp4"
        
        print("Starting video processing with text recognition...")
        print("Press 'q' to stop processing (if GUI is available)")
        print("Press Ctrl+C to stop processing in console mode")
        
        detector.process_video(video_path, output_path, display=True)
        
    except Exception as e:
        print(f"Error: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure model file exists")
        print("2. Make sure video file exists")
        print("3. Try running without display: set display=False")

if __name__ == "__main__":
    main()