class ObjectDetectionProcessor {
  constructor() {
    this.baseUrl = "http://localhost:5000/api";
    this.controller = null;
    this.modelName = "object_detection"; // Fixed model for this page
  }

  async processVideo(videoFile) {
    // Abort any previous request
    if (this.controller) {
      this.controller.abort();
    }

    this.controller = new AbortController();
    const formData = new FormData();
    formData.append("video", videoFile);
    formData.append("model_type", this.modelName);

    try {
      this.showLoading(true);
      console.log(`⏳ Starting object detection...`);

      const timeoutId = setTimeout(() => this.controller.abort(), 600000); // 10 minutes

      const res = await fetch(`${this.baseUrl}/process_video`, {
        method: "POST",
        body: formData,
        signal: this.controller.signal,
      });

      clearTimeout(timeoutId);

      console.log("✅ Fetch completed. Status:", res.status, res.statusText);

      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(`Server returned ${res.status}: ${errorText}`);
      }

      const data = await res.json();

      if (data.success && data.output_file) {
        const streamUrl = `${this.baseUrl}/stream/${data.output_file}`;
        const downloadUrl = `${this.baseUrl}/download/${data.output_file}`;

        console.log("🔗 Stream URL:", streamUrl);
        console.log("🔗 Download URL:", downloadUrl);

        return {
          success: true,
          streamUrl: streamUrl,
          downloadUrl: downloadUrl,
          fileId: data.output_file,
          message: data.message || "Object detection completed successfully!",
        };
      } else {
        return {
          success: false,
          error: data.error || data.message || "Unknown server error",
        };
      }
    } catch (err) {
      console.error("🔴 FETCH ERROR DETAILS:");
      console.error("Name:", err.name);
      console.error("Message:", err.message);
      console.error("Stack:", err.stack);

      if (err.name === "AbortError") {
        return {
          success: false,
          error: "Processing timeout: Video is too long or server is busy",
        };
      }
      if (err.name === "TypeError" && err.message.includes("failed to fetch")) {
        return {
          success: false,
          error:
            "Network error: Cannot connect to server. Make sure Flask is running on localhost:5000",
        };
      }
      return { success: false, error: err.message };
    } finally {
      this.showLoading(false);
      this.controller = null;
      console.log("🧹 Cleanup completed");
    }
  }

  showLoading(show) {
    let loader = document.getElementById("object-detection-loading-indicator");
    if (!loader && show) {
      loader = document.createElement("div");
      loader.id = "object-detection-loading-indicator";
      loader.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px;">
          <i class="fas fa-search fa-spin"></i>
          <span>Detecting objects... Please wait</span>
        </div>
      `;
      loader.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: rgba(0, 0, 0, 0.9);
        color: white;
        padding: 20px 30px;
        border-radius: 10px;
        z-index: 10000;
        font-family: Arial, sans-serif;
        border: 2px solid #00ff00;
      `;
      document.body.appendChild(loader);
    }
    if (loader) {
      loader.style.display = show ? "flex" : "none";
    }
  }

  cancelProcessing() {
    if (this.controller) {
      this.controller.abort();
      this.showLoading(false);
      console.log("❌ Object detection cancelled");
    }
  }
}

// Initialize Processor
const objectDetectionProcessor = new ObjectDetectionProcessor();

// DOM Content Loaded
document.addEventListener("DOMContentLoaded", () => {
  initializeObjectDetectionForm();
});

function initializeObjectDetectionForm() {
  const videoFileInput = document.getElementById("videoFile");
  const fileNameDisplay = document.getElementById("fileNameDisplay");
  const uploadForm = document.getElementById("videoUploadForm");

  if (!uploadForm) {
    console.error("❌ Object detection upload form not found!");
    return;
  }

  const analyzeButton = uploadForm.querySelector('button[type="submit"]');
  let cancelButton = document.getElementById("objectDetectionCancelButton");

  // Create cancel button if it doesn't exist
  if (!cancelButton && analyzeButton) {
    cancelButton = document.createElement("button");
    cancelButton.id = "objectDetectionCancelButton";
    cancelButton.type = "button";
    cancelButton.innerHTML = '<i class="fas fa-times"></i> Cancel Processing';
    cancelButton.style.cssText = `
      background: #ff4444;
      color: white;
      padding: 10px 20px;
      border: none;
      border-radius: 5px;
      cursor: pointer;
      margin-left: 10px;
      display: none;
      font-family: inherit;
    `;
    cancelButton.addEventListener("click", () => {
      objectDetectionProcessor.cancelProcessing();
      cancelButton.style.display = "none";
      if (analyzeButton) {
        analyzeButton.disabled = false;
        analyzeButton.innerHTML = '<i class="fas fa-play"></i> Analyze Video';
      }
    });
    analyzeButton.parentNode.appendChild(cancelButton);
  }

  // File selection display
  if (videoFileInput) {
    videoFileInput.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (file) {
        // Validate file type
        const validTypes = [
          "video/mp4",
          "video/avi",
          "video/mov",
          "video/mkv",
          "video/webm",
        ];
        if (!validTypes.includes(file.type)) {
          alert(
            "Please select a valid video file (MP4, AVI, MOV, MKV, or WEBM)."
          );
          e.target.value = "";
          if (fileNameDisplay) fileNameDisplay.textContent = "";
          return;
        }

        // Validate file size (100MB limit)
        if (file.size > 100 * 1024 * 1024) {
          alert(
            "Video file is too large. Please select a file smaller than 100MB."
          );
          e.target.value = "";
          if (fileNameDisplay) fileNameDisplay.textContent = "";
          return;
        }

        if (fileNameDisplay) {
          fileNameDisplay.textContent = `Selected: ${file.name} (${(
            file.size /
            (1024 * 1024)
          ).toFixed(2)} MB)`;
          fileNameDisplay.style.color = "#00EAFF";
        }
      } else {
        if (fileNameDisplay) fileNameDisplay.textContent = "";
      }
    });
  }

  // Form submission
  uploadForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    if (!videoFileInput || videoFileInput.files.length === 0) {
      alert("Please select a video file to upload.");
      return;
    }

    const videoFile = videoFileInput.files[0];

    // Update button states
    if (analyzeButton) {
      analyzeButton.disabled = true;
      analyzeButton.innerHTML =
        '<i class="fas fa-spinner fa-spin"></i> Detecting Objects...';
    }
    if (cancelButton) {
      cancelButton.style.display = "inline-block";
    }

    try {
      console.log("🔄 Starting object detection...");
      const result = await objectDetectionProcessor.processVideo(videoFile);

      if (result.success) {
        console.log("✅ Object detection successful!");
        showObjectDetectionResults(result);
        if (fileNameDisplay) {
          fileNameDisplay.textContent =
            "✅ Object detection complete! Video ready below.";
          fileNameDisplay.style.color = "#00ff00";
        }
      } else {
        alert("Object Detection Error: " + result.error);
        if (fileNameDisplay) {
          fileNameDisplay.textContent = "❌ Object detection failed";
          fileNameDisplay.style.color = "#ff0000";
        }
      }
    } catch (error) {
      console.error("Unexpected error:", error);
      alert("Unexpected error: " + error.message);
      if (fileNameDisplay) {
        fileNameDisplay.textContent = "❌ Object detection failed";
        fileNameDisplay.style.color = "#ff0000";
      }
    } finally {
      // Reset button states
      if (analyzeButton) {
        analyzeButton.disabled = false;
        analyzeButton.innerHTML = '<i class="fas fa-play"></i> Analyze Video';
      }
      if (cancelButton) {
        cancelButton.style.display = "none";
      }
    }
  });
}

function showObjectDetectionResults(result) {
  let processedVideoContainer = document.getElementById(
    "processedVideoContainer"
  );
  if (!processedVideoContainer) {
    processedVideoContainer = document.createElement("div");
    processedVideoContainer.id = "processedVideoContainer";
    processedVideoContainer.style.marginTop = "20px";
    const uploadForm = document.getElementById("videoUploadForm");
    if (uploadForm) {
      uploadForm.appendChild(processedVideoContainer);
    } else {
      document.body.appendChild(processedVideoContainer);
    }
  }

  processedVideoContainer.innerHTML = `
    <div style="background: rgba(0, 255, 0, 0.1); padding: 20px; border-radius: 10px; border: 2px solid #00ff00;">
      <h3 style="color: #00ff00; margin-bottom: 15px; display: flex; align-items: center; gap: 10px;">
        <i class="fas fa-check-circle"></i>
        Object Detection Complete!
      </h3>
      <div style="display: flex; flex-direction: column; gap: 15px;">
        <video controls width="100%" style="border-radius: 10px; max-width: 800px; background: #000; border: 2px solid #00ff00;">
          <source src="${result.streamUrl}" type="video/mp4">
          Your browser does not support the video tag.
        </video>
        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
          <a href="${result.downloadUrl}" 
             download="object_detected_video.mp4" 
             style="background: #00ff00; color: black; padding: 12px 24px; border-radius: 5px; text-decoration: none; display: inline-flex; align-items: center; gap: 8px; font-weight: bold;">
            <i class="fas fa-download"></i> Download Processed Video
          </a>
          <button onclick="processAnotherVideo()" 
                  style="background: #666; color: white; padding: 12px 24px; border: none; border-radius: 5px; cursor: pointer; display: inline-flex; align-items: center; gap: 8px;">
            <i class="fas fa-redo"></i> Analyze Another Video
          </button>
        </div>
        <div style="color: #666; font-size: 14px; margin-top: 10px;">
          <i class="fas fa-info-circle"></i> Detected objects are highlighted in green bounding boxes
        </div>
      </div>
    </div>
  `;

  // Scroll to results
  processedVideoContainer.scrollIntoView({ behavior: "smooth" });
}

function processAnotherVideo() {
  // Reset the form
  const uploadForm = document.getElementById("videoUploadForm");
  if (uploadForm) {
    uploadForm.reset();
  }

  // Clear file display
  const fileNameDisplay = document.getElementById("fileNameDisplay");
  if (fileNameDisplay) {
    fileNameDisplay.textContent = "";
  }

  // Remove results
  const processedVideoContainer = document.getElementById(
    "processedVideoContainer"
  );
  if (processedVideoContainer) {
    processedVideoContainer.remove();
  }

  // Scroll to top
  window.scrollTo({ top: 0, behavior: "smooth" });
}
