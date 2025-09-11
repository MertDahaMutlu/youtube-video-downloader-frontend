// script.js - works with main.py above
const API_BASE = "http://127.0.0.1:8000"; // change if backend is on different host/port

const urlInput = document.getElementById("url");
const qualitySelect = document.getElementById("quality");
const downloadVideoBtn = document.getElementById("downloadVideo");
const downloadAudioBtn = document.getElementById("downloadAudio");
const statusDiv = document.getElementById("status");

function setStatus(msg, isError=false){
  statusDiv.textContent = msg;
  statusDiv.style.color = isError ? "#ffb4b4" : "";
}

async function pollStatusAndDownload(jobId){
  setStatus("Processing...");
  const pollInterval = 1000;
  return new Promise((resolve, reject) => {
    const t = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/status/${jobId}`);
        if (!res.ok) {
          clearInterval(t);
          const txt = await res.text().catch(()=>res.statusText);
          setStatus("Status error: " + txt, true);
          reject(new Error("status error"));
          return;
        }
        const j = await res.json();
        if (j.status === "processing") {
          setStatus("Processing...");
          return;
        } else if (j.status === "failed") {
          clearInterval(t);
          setStatus("Download failed: " + (j.error || "unknown"), true);
          reject(new Error(j.error || "failed"));
          return;
        } else if (j.status === "done") {
          clearInterval(t);
          setStatus("Ready — starting download...");
          // download_url might be relative like /downloads/xxx.mp4
          let downloadUrl = j.download_url;
          if (downloadUrl.startsWith("/")) downloadUrl = API_BASE + downloadUrl;
          try {
            const fileRes = await fetch(downloadUrl);
            if (!fileRes.ok) throw new Error("file GET failed " + fileRes.status);
            const blob = await fileRes.blob();
            // try to get filename from Content-Disposition header
            let filename = "download";
            const cd = fileRes.headers.get("content-disposition") || fileRes.headers.get("Content-Disposition");
            if (cd) {
              const m = cd.match(/filename\*?=(?:UTF-8'')?["']?([^;"']+)/i);
              if (m && m[1]) filename = decodeURIComponent(m[1]);
            } else {
              // fallback: last part of URL
              filename = downloadUrl.split("/").pop();
            }
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            setStatus("Download finished ✅");
            resolve();
          } catch (err) {
            setStatus("Download error: " + err.message, true);
            reject(err);
          }
        } else {
          clearInterval(t);
          setStatus("Unknown status", true);
          reject(new Error("unknown status"));
        }
      } catch (err) {
        clearInterval(t);
        setStatus("Network error: " + err.message, true);
        reject(err);
      }
    }, pollInterval);
  });
}

downloadVideoBtn.addEventListener("click", async () => {
  const url = urlInput.value.trim();
  const quality = qualitySelect.value || "best";
  if (!url) { setStatus("Please paste a YouTube URL", true); return; }

  setStatus("Starting job...");
  const fd = new FormData();
  fd.append("url", url);
  fd.append("quality", quality);

  try {
    const res = await fetch(`${API_BASE}/download`, { method: "POST", body: fd });
    if (!res.ok) {
      const txt = await res.text().catch(()=>res.statusText);
      setStatus("Start error: " + txt, true);
      return;
    }
    const j = await res.json();
    const jobId = j.job_id;
    await pollStatusAndDownload(jobId);
  } catch (err) {
    setStatus("Error: " + err.message, true);
    console.error(err);
  }
});

downloadAudioBtn.addEventListener("click", async () => {
  const url = urlInput.value.trim();
  if (!url) { setStatus("Please paste a YouTube URL", true); return; }

  setStatus("Starting audio job...");
  const fd = new FormData();
  fd.append("url", url);

  try {
    const res = await fetch(`${API_BASE}/download-audio`, { method: "POST", body: fd });
    if (!res.ok) {
      const txt = await res.text().catch(()=>res.statusText);
      setStatus("Start error: " + txt, true);
      return;
    }
    const j = await res.json();
    const jobId = j.job_id;
    await pollStatusAndDownload(jobId);
  } catch (err) {
    setStatus("Error: " + err.message, true);
    console.error(err);
  }
});
