import cv2
import supervision as sv
from ultralytics import YOLO
import os
import time
import torch
import torch.nn as nn
from ultralytics.nn.modules import block

# Add compatibility fixes
class AAttn(nn.Module):
    def __init__(self, *args, **kwargs):
        super().__init__()
    def forward(self, x):
        return x

block.C3k2 = block.C3
block.A2C2f = block.C2f  
block.ABlock = block.C2f
block.C3Ghost = block.C3
block.C3x = block.C3
block.SPPF = block.SPP
block.Bottleneck = block.Conv
block.RepC3 = block.C3
block.ELAN = block.C2f
block.MP = block.Conv
block.SPPCSPC = block.SPP
block.AAttn = AAttn
block.C3k = block.C3

print("🔧 Loading helmet model...")
model = YOLO("models/best.pt")
print("✅ Helmet Model loaded!")
print("🎯 Model classes:", model.names)

def process_video(input_path, output_path, alert_callback=None):
    """
    Your original working code adapted for Flask
    """
    print(f"\n🎬 Processing: {input_path} -> {output_path}")
    
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise Exception(f"❌ Could not open video: {input_path}")

    # Get video properties
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Define video writer
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    bounding_box_annotator = sv.BoxAnnotator()
    label_annotator = sv.LabelAnnotator()

    frame_count = 0
    total_detections = 0
    start_time = time.time()

    print("🚀 Processing started...")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1

        # Run YOLO detection - EXACTLY like your working code
        results = model(frame)[0]
        detections = sv.Detections.from_ultralytics(results)

        # Count detections
        if len(detections) > 0:
            total_detections += len(detections)
            print(f"🎯 Frame {frame_count}: Detected {len(detections)} objects")
            for i, (class_id, confidence) in enumerate(zip(detections.class_id, detections.confidence)):
                class_name = model.names[class_id]
                print(f"   - {class_name}: {confidence:.3f}")

        # Annotate frame
        annotated_frame = bounding_box_annotator.annotate(scene=frame, detections=detections)
        annotated_frame = label_annotator.annotate(scene=annotated_frame, detections=detections)

        # Write the frame
        out.write(annotated_frame)

        # Progress
        if frame_count % 50 == 0:
            elapsed = time.time() - start_time
            fps_actual = frame_count / elapsed
            print(f"📊 Progress: {frame_count} frames, {fps_actual:.1f} FPS")

    cap.release()
    out.release()
    
    total_time = time.time() - start_time
    print(f"\n✅ Processing complete!")
    print(f"📊 Frames: {frame_count}, Detections: {total_detections}, Time: {total_time:.2f}s")
    print(f"💾 Output: {output_path}")

    return output_path, []

# Flask compatibility
def get_alert_history():
    return []

def clear_alert_history():
    pass
