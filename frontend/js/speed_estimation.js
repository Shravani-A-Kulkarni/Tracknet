class SpeedEstimationProcessor {
  constructor() {
    this.baseUrl = "http://localhost:5000/api";
    this.controller = null;
    this.modelName = "speed_estimation"; // Fixed model for this page
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
      console.log(`⏳ Starting speed estimation...`);

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
      console.log("📦 Server response:", data); // Debug log

      if (data.success) {
        // Get the file ID from output_path or output_file
        const fileId = data.output_path
          ? data.output_path.split("_").pop().replace(".mp4", "")
          : data.output_file
          ? data.output_file
          : null;

        if (!fileId) {
          throw new Error("Could not get output file ID from server response");
        }

        const streamUrl = `${this.baseUrl}/stream/processed_${fileId}.mp4`;
        const downloadUrl = `${this.baseUrl}/download/processed_${fileId}.mp4`;

        console.log("🔗 Stream URL:", streamUrl);
        console.log("🔗 Download URL:", downloadUrl);
        console.log(
          "🚨 Speed alerts received:",
          data.alerts ? data.alerts.length : 0
        );

        return {
          success: true,
          streamUrl: streamUrl,
          downloadUrl: downloadUrl,
          fileId: fileId,
          alerts: data.alerts || [], // Make sure alerts are included
          message: data.message || "Speed estimation completed successfully!",
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
    let loader = document.getElementById("speed-estimation-loading-indicator");
    if (!loader && show) {
      loader = document.createElement("div");
      loader.id = "speed-estimation-loading-indicator";
      loader.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px;">
          <i class="fas fa-tachometer-alt fa-spin"></i>
          <span>Estimating speeds... Please wait</span>
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
        border: 2px solid #FF4444;
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
      console.log("❌ Speed estimation cancelled");
    }
  }
}

// Initialize Processor
const speedEstimationProcessor = new SpeedEstimationProcessor();

// DOM Content Loaded
document.addEventListener("DOMContentLoaded", () => {
  initializeSpeedEstimationForm();
});

function initializeSpeedEstimationForm() {
  const videoFileInput = document.getElementById("videoFile");
  const fileNameDisplay = document.getElementById("fileNameDisplay");
  const uploadForm = document.getElementById("videoUploadForm");

  if (!uploadForm) {
    console.error("❌ Speed estimation upload form not found!");
    return;
  }

  const analyzeButton = uploadForm.querySelector('button[type="submit"]');
  let cancelButton = document.getElementById("speedEstimationCancelButton");

  // Create cancel button if it doesn't exist
  if (!cancelButton && analyzeButton) {
    cancelButton = document.createElement("button");
    cancelButton.id = "speedEstimationCancelButton";
    cancelButton.type = "button";
    cancelButton.innerHTML = '<i class="fas fa-times"></i> Cancel Estimation';
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
      speedEstimationProcessor.cancelProcessing();
      cancelButton.style.display = "none";
      if (analyzeButton) {
        analyzeButton.disabled = false;
        analyzeButton.innerHTML =
          '<i class="fas fa-tachometer-alt"></i> Estimate Speeds';
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
          fileNameDisplay.style.color = "#FF4444";
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
        '<i class="fas fa-spinner fa-spin"></i> Estimating Speeds...';
    }
    if (cancelButton) {
      cancelButton.style.display = "inline-block";
    }

    try {
      console.log("🔄 Starting speed estimation...");
      const result = await speedEstimationProcessor.processVideo(videoFile);

      if (result.success) {
        console.log("✅ Speed estimation successful!");
        console.log("📦 Result object:", result); // Debug log
        console.log(
          `📊 Speed alerts detected: ${
            result.alerts ? result.alerts.length : 0
          }`
        );

        showSpeedEstimationResults(result);

        if (fileNameDisplay) {
          const alertCount = result.alerts ? result.alerts.length : 0;
          fileNameDisplay.textContent = `✅ Speed estimation complete! ${alertCount} speed alerts detected.`;
          fileNameDisplay.style.color = alertCount > 0 ? "#ff4444" : "#00ff00";
        }
      } else {
        console.error("❌ Estimation failed:", result.error);
        alert("Speed Estimation Error: " + result.error);
        if (fileNameDisplay) {
          fileNameDisplay.textContent = "❌ Speed estimation failed";
          fileNameDisplay.style.color = "#ff0000";
        }
      }
    } catch (error) {
      console.error("Unexpected error:", error);
      alert("Unexpected error: " + error.message);
      if (fileNameDisplay) {
        fileNameDisplay.textContent = "❌ Speed estimation failed";
        fileNameDisplay.style.color = "#ff0000";
      }
    } finally {
      // Reset button states
      if (analyzeButton) {
        analyzeButton.disabled = false;
        analyzeButton.innerHTML =
          '<i class="fas fa-tachometer-alt"></i> Estimate Speeds';
      }
      if (cancelButton) {
        cancelButton.style.display = "none";
      }
    }
  });
}

function showSpeedEstimationResults(result) {
  console.log("🎯 Showing speed results:", result); // Debug log

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

  // Show alert notification if there are speed alerts
  if (result.alerts && result.alerts.length > 0) {
    showSpeedAlertNotification(result.alerts.length);
    console.log(
      "🚨 Showing speed alert notification for",
      result.alerts.length,
      "alerts"
    );
  } else {
    console.log("ℹ️ No speed alerts to show");
  }

  // Create the video player UI - KEEP THE ORIGINAL STYLING
  processedVideoContainer.innerHTML = `
    <div style="background: rgba(255, 68, 68, 0.1); padding: 20px; border-radius: 10px; border: 2px solid #FF4444;">
      <h3 style="color: #FF4444; margin-bottom: 15px; display: flex; align-items: center; gap: 10px;">
        <i class="fas fa-tachometer-alt"></i>
        Speed Estimation Complete!
      </h3>
      <div style="display: flex; flex-direction: column; gap: 15px;">
        <video controls width="100%" style="border-radius: 10px; max-width: 800px; background: #000; border: 2px solid #FF4444;">
          <source src="${result.streamUrl}" type="video/mp4">
          Your browser does not support the video tag.
        </video>
        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
          <a href="${result.downloadUrl}" 
             download="speed_estimation_video.mp4" 
             style="background: #FF4444; color: white; padding: 12px 24px; border-radius: 5px; text-decoration: none; display: inline-flex; align-items: center; gap: 8px; font-weight: bold;">
            <i class="fas fa-download"></i> Download Processed Video
          </a>
          <button onclick="processAnotherVideo()" 
                  style="background: #666; color: white; padding: 12px 24px; border: none; border-radius: 5px; cursor: pointer; display: inline-flex; align-items: center; gap: 8px;">
            <i class="fas fa-redo"></i> Estimate Another Video
          </button>
        </div>
        <div style="color: #666; font-size: 14px; margin-top: 10px;">
          <i class="fas fa-info-circle"></i> 
          <strong>Color Coding:</strong> 
          <span style="color: #00ff00;">Green</span> = Low Speed (&lt;30 km/h), 
          <span style="color: #ffa500;">Orange</span> = Medium Speed (30-50 km/h), 
          <span style="color: #ff4444;">Red</span> = High Speed (&gt;50 km/h)
          ${
            result.alerts && result.alerts.length > 0
              ? `<br><i class="fas fa-exclamation-triangle" style="color: #ff4444;"></i> 
             <span style="color: #ff4444;">${result.alerts.length} speeding alerts detected</span>`
              : ""
          }
        </div>
      </div>
    </div>
  `;

  // Scroll to results
  processedVideoContainer.scrollIntoView({ behavior: "smooth" });
  console.log("✅ Speed results displayed successfully");
}

// NEW: Function to show speed alert notification
function showSpeedAlertNotification(alertCount) {
  // Create notification element
  const notification = document.createElement("div");
  notification.innerHTML = `
    <div style="position: fixed; top: 20px; right: 20px; background: #ff4444; color: white; padding: 15px 20px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); z-index: 10000; max-width: 300px;">
      <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
        <i class="fas fa-tachometer-alt" style="font-size: 18px;"></i>
        <strong style="font-size: 16px;">Speeding Alert!</strong>
      </div>
      <div style="font-size: 14px;">
        ${alertCount} vehicle${alertCount > 1 ? "s" : ""} exceeded speed limit
      </div>
      <button onclick="this.parentElement.parentElement.remove()" 
              style="position: absolute; top: 8px; right: 8px; background: none; border: none; color: white; cursor: pointer; font-size: 16px;">
        <i class="fas fa-times"></i>
      </button>
    </div>
  `;

  document.body.appendChild(notification);

  // Auto-remove after 5 seconds
  setTimeout(() => {
    if (notification.parentElement) {
      notification.remove();
    }
  }, 5000);
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
