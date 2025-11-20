import cv2
from ultralytics import YOLO

# -----------------------------
# Load your model
# -----------------------------
model = YOLO("best.pt")  # change path if needed

# -----------------------------
# Input and Output video paths
# -----------------------------
input_video = "test_video.mp4"       # put your video name
output_video = "output_result.mp4"

# -----------------------------
# Video reading
# -----------------------------
cap = cv2.VideoCapture(input_video)

if not cap.isOpened():
    print("❌ Error: Could not open input video")
    exit()

# Video writer (same FPS and size as input)
fourcc = cv2.VideoWriter_fourcc(*"mp4v")
fps = int(cap.get(cv2.CAP_PROP_FPS))
width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

out = cv2.VideoWriter(output_video, fourcc, fps, (width, height))

# -----------------------------
# Process video frame-by-frame
# -----------------------------
while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Run YOLO prediction on frame
    results = model.predict(frame, conf=0.4)

    # Extract predictions
    for r in results:
        boxes = r.boxes  # bounding boxes
        for box in boxes:
            # Bounding box coordinates
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)

            # Class ID and confidence
            cls = int(box.cls[0])
            conf = float(box.conf[0])

            label = model.names[cls] if model.names else f"Class {cls}"

            # Color: green=Helmet, red=No Helmet
            color = (0, 255, 0) if "helmet" in label.lower() else (0, 0, 255)

            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)

            # Draw label
            cv2.putText(
                frame,
                f"{label} {conf:.2f}",
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                color,
                2
            )

    # Write output video
    out.write(frame)

    # Show live output
    cv2.imshow("Helmet Detection", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# -----------------------------
# Cleanup
# -----------------------------
cap.release()
out.release()
cv2.destroyAllWindows()

print("✔ Processing complete! Saved output as:", output_video)
