// frontend/script.js

// CHANGE THIS to your backend deployment URL when you deploy.
// For local testing keep it: http://127.0.0.1:5000
const API_BASE = "http://127.0.0.1:8080";

const urlInput = document.getElementById("url");
const qualitySelect = document.getElementById("quality");
const downloadVideoBtn = document.getElementById("downloadVideo");
const downloadAudioBtn = document.getElementById("downloadAudio");
const status = document.getElementById("status");

function setStatus(txt, isError=false){
  status.textContent = txt;
  status.style.color = isError ? "#ffb4b4" : "";
}

async function fetchAndDownload(queryString, suggestedName) {
  setStatus("Processing...");
  try {
    const res = await fetch(queryString);
    if (!res.ok) {
      const json = await res.json().catch(()=>null);
      setStatus("Error: " + (json?.error || res.statusText), true);
      return;
    }
    const blob = await res.blob();
    // get filename from content-disposition if possible
    let filename = suggestedName || "download";
    const cd = res.headers.get("Content-Disposition");
    if (cd) {
      const match = cd.match(/filename\*?=(?:UTF-8'')?["']?([^;"']+)/i);
      if (match && match[1]) filename = decodeURIComponent(match[1]);
    }
    // set extension if not present
    if (!filename.includes(".")) {
      const ct = res.headers.get("Content-Type");
      if (ct && ct.includes("audio")) filename += ".mp3";
      else filename += ".mp4";
    }
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setStatus("Download started ✅");
  } catch (err) {
    console.error(err);
    setStatus("Network or server error", true);
  }
}

downloadVideoBtn.addEventListener("click", () => {
  const url = urlInput.value.trim();
  if (!url) { setStatus("Please paste a YouTube URL", true); return; }
  const quality = qualitySelect.value;
  const qs = `${API_BASE}/download?url=${encodeURIComponent(url)}&type=video&quality=${encodeURIComponent(quality)}`;
  fetchAndDownload(qs, "video.mp4");
});

downloadAudioBtn.addEventListener("click", () => {
  const url = urlInput.value.trim();
  if (!url) { setStatus("Please paste a YouTube URL", true); return; }
  const qs = `${API_BASE}/download?url=${encodeURIComponent(url)}&type=audio`;
  fetchAndDownload(qs, "audio.mp3");
});
