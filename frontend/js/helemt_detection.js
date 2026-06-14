class HelmetDetectionProcessor {
  constructor() {
    this.baseUrl = "http://localhost:5000/api";
    this.controller = null;
    this.modelName = "helmet_detection";
  }

  async processVideo(videoFile) {
    if (this.controller) this.controller.abort();

    this.controller = new AbortController();
    const formData = new FormData();
    formData.append("video", videoFile);
    formData.append("model_type", this.modelName);

    try {
      this.showLoading(true);
      console.log("🪖 Starting helmet detection...");
      console.log("📤 Sending request to:", `${this.baseUrl}/process_video`);
      console.log("🎯 Model type:", this.modelName);
      console.log("📹 Video file:", videoFile.name, videoFile.size, "bytes");

      const timeoutId = setTimeout(() => this.controller.abort(), 600000);

      // ADD THIS: Log the request details
      console.log("🔍 Request details:", {
        url: `${this.baseUrl}/process_video`,
        method: "POST",
        hasFile: !!videoFile,
        fileSize: videoFile.size,
        modelType: this.modelName,
      });

      const res = await fetch(`${this.baseUrl}/process_video`, {
        method: "POST",
        body: formData,
        signal: this.controller.signal,
      });

      console.log("✅ Response received. Status:", res.status, res.statusText);
      console.log(
        "📨 Response headers:",
        Object.fromEntries(res.headers.entries()),
      );

      clearTimeout(timeoutId);

      if (!res.ok) {
        const errorText = await res.text();
        console.log("❌ Response error text:", errorText);
        throw new Error(`Server returned ${res.status}: ${errorText}`);
      }

      const data = await res.json();
      console.log("📊 Response data:", data);

      if (data.success) {
        // Get the file ID from output_path or output_file
        const fileId = data.output_file
          ? data.output_file.replace("processed_", "").replace(".mp4", "")
          : null;

        if (!fileId) {
          throw new Error("Could not get output file from server response");
        }

        const streamUrl = `${this.baseUrl}/stream/processed_${fileId}.mp4`;
        const downloadUrl = `${this.baseUrl}/download/processed_${fileId}.mp4`;

        return {
          success: true,
          streamUrl,
          downloadUrl,
          message: data.message || "Helmet detection completed successfully!",
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
            "Network error: Cannot connect to Flask. Make sure it's running on localhost:5000.",
        };
      }
      return { success: false, error: err.message };
    } finally {
      this.showLoading(false);
      this.controller = null;
      console.log("🧹 Cleanup complete");
    }
  }

  showLoading(show) {
    let loader = document.getElementById("helmet-detection-loading");
    if (!loader && show) {
      loader = document.createElement("div");
      loader.id = "helmet-detection-loading";
      loader.innerHTML = `
        <div style="display:flex;align-items:center;gap:10px;">
          <i class="fas fa-hard-hat fa-spin"></i>
          <span>Detecting helmets... Please wait</span>
        </div>
      `;
      loader.style.cssText = `
        position:fixed;
        top:50%;left:50%;
        transform:translate(-50%,-50%);
        background:rgba(0,0,0,0.85);
        color:#fff;
        padding:20px 30px;
        border-radius:10px;
        font-family:Arial, sans-serif;
        z-index:10000;
        border:2px solid #00ffea;
      `;
      document.body.appendChild(loader);
    }
    if (loader) loader.style.display = show ? "flex" : "none";
  }

  cancelProcessing() {
    if (this.controller) {
      this.controller.abort();
      this.showLoading(false);
      console.log("❌ Helmet detection cancelled");
    }
  }
}

// Initialize Processor
const helmetProcessor = new HelmetDetectionProcessor();

document.addEventListener("DOMContentLoaded", () => {
  initializeHelmetDetectionForm();
});

function initializeHelmetDetectionForm() {
  const videoInput = document.getElementById("videoFile");
  const fileNameDisplay = document.getElementById("fileNameDisplay");
  const uploadForm = document.getElementById("videoUploadForm");

  if (!uploadForm) {
    console.error("❌ Helmet detection upload form not found!");
    return;
  }

  const analyzeButton = uploadForm.querySelector('button[type="submit"]');
  let cancelButton = document.getElementById("helmetCancelButton");

  if (!cancelButton && analyzeButton) {
    cancelButton = document.createElement("button");
    cancelButton.id = "helmetCancelButton";
    cancelButton.type = "button";
    cancelButton.innerHTML = '<i class="fas fa-times"></i> Cancel Processing';
    cancelButton.style.cssText = `
      background:#ff4444;color:white;padding:10px 20px;border:none;
      border-radius:5px;cursor:pointer;margin-left:10px;font-family:inherit;
      display:none;
    `;
    cancelButton.addEventListener("click", () => {
      helmetProcessor.cancelProcessing();
      cancelButton.style.display = "none";
      analyzeButton.disabled = false;
      analyzeButton.innerHTML = '<i class="fas fa-play"></i> Analyze Video';
    });
    analyzeButton.parentNode.appendChild(cancelButton);
  }

  // File selection
  videoInput.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) {
      const validTypes = [
        "video/mp4",
        "video/avi",
        "video/mov",
        "video/mkv",
        "video/webm",
      ];
      if (!validTypes.includes(file.type)) {
        alert("Invalid file. Please select MP4, AVI, MOV, MKV, or WEBM.");
        e.target.value = "";
        fileNameDisplay.textContent = "";
        return;
      }

      if (file.size > 100 * 1024 * 1024) {
        alert("File too large. Please select under 100MB.");
        e.target.value = "";
        fileNameDisplay.textContent = "";
        return;
      }

      fileNameDisplay.textContent = `Selected: ${file.name}`;
      fileNameDisplay.style.color = "#00EAFF";
    } else {
      fileNameDisplay.textContent = "";
    }
  });

  // Submit form
  uploadForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    e.stopPropagation();

    if (!videoInput.files.length) {
      alert("Please select a video first.");
      return;
    }

    const videoFile = videoInput.files[0];

    analyzeButton.disabled = true;
    analyzeButton.innerHTML =
      '<i class="fas fa-spinner fa-spin"></i> Detecting Helmets...';
    cancelButton.style.display = "inline-block";

    try {
      console.log("🎥 Sending video to backend for helmet detection...");
      const result = await helmetProcessor.processVideo(videoFile);

      if (result.success) {
        showHelmetDetectionResults(result);
        fileNameDisplay.textContent =
          "✅ Helmet detection complete! Video ready below.";
        fileNameDisplay.style.color = "#00ff00";
      } else {
        alert("Helmet Detection Error: " + result.error);
        fileNameDisplay.textContent = "❌ Helmet detection failed";
        fileNameDisplay.style.color = "#ff0000";
      }
    } catch (err) {
      console.error(err);
      alert("Unexpected error: " + err.message);
      fileNameDisplay.textContent = "❌ Helmet detection failed";
      fileNameDisplay.style.color = "#ff0000";
    } finally {
      analyzeButton.disabled = false;
      analyzeButton.innerHTML = '<i class="fas fa-play"></i> Analyze Video';
      cancelButton.style.display = "none";
    }
  });
}

function showHelmetDetectionResults(result) {
  let container = document.getElementById("helmetVideoContainer");
  if (!container) {
    container = document.createElement("div");
    container.id = "helmetVideoContainer";
    container.style.marginTop = "20px";
    document.getElementById("videoUploadForm").appendChild(container);
  }

  container.innerHTML = `
    <div style="background:rgba(0,255,234,0.1);padding:20px;border-radius:10px;border:2px solid #00ffea;">
      <h3 style="color:#00ffea;margin-bottom:15px;display:flex;align-items:center;gap:10px;">
        <i class="fas fa-hard-hat"></i>
        Helmet Detection Complete!
      </h3>
      <video controls width="100%" style="border-radius:10px;max-width:800px;background:#000;border:2px solid #00ffea;">
        <source src="${result.streamUrl}" type="video/mp4">
      </video>
      <div style="display:flex;gap:10px;margin-top:15px;flex-wrap:wrap;">
        <a href="${result.downloadUrl}" download="helmet_detected_video.mp4"
           style="background:#00ffea;color:black;padding:12px 24px;border-radius:5px;text-decoration:none;font-weight:bold;display:inline-flex;align-items:center;gap:8px;">
          <i class="fas fa-download"></i> Download Processed Video
        </a>
        <button onclick="processAnotherHelmetVideo()" 
          style="background:#666;color:white;padding:12px 24px;border:none;border-radius:5px;cursor:pointer;display:inline-flex;align-items:center;gap:8px;">
          <i class="fas fa-redo"></i> Analyze Another Video
        </button>
      </div>
      <p style="color:#888;font-size:14px;margin-top:10px;">
        <i class="fas fa-info-circle"></i> Detected riders with and without helmets are marked accordingly.
      </p>
    </div>
  `;

  container.scrollIntoView({ behavior: "smooth" });
}

function processAnotherHelmetVideo() {
  const uploadForm = document.getElementById("videoUploadForm");
  uploadForm.reset();
  document.getElementById("fileNameDisplay").textContent = "";
  const container = document.getElementById("helmetVideoContainer");
  if (container) container.remove();
  window.scrollTo({ top: 0, behavior: "smooth" });
}
