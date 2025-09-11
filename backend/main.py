# main.py
# FastAPI backend using yt-dlp + ffmpeg fallback to ensure MP4/AAC for Windows.
# English comments (global) as requested.

import os
import uuid
import glob
import mimetypes
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

import yt_dlp

# ----- CONFIG -----
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Thread-safe job store: job_id -> dict(status: processing|done|failed, filename(optional), error(optional))
jobs: Dict[str, Dict] = {}
jobs_lock = threading.Lock()

# Executor for blocking downloads
executor = ThreadPoolExecutor(max_workers=2)

app = FastAPI(title="YouTube Downloader (yt-dlp + ffmpeg)")

# Allow all origins for development (adjust for prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def find_downloaded_file(job_id: str):
    """Find a file in downloads that starts with job_id.* and return basename or None."""
    pattern = os.path.join(DOWNLOAD_DIR, f"{job_id}.*")
    files = glob.glob(pattern)
    if not files:
        return None
    # prefer mp4/mp3
    for ext in (".mp4", ".mp3", ".mkv", ".webm"):
        for f in files:
            if f.lower().endswith(ext):
                return os.path.basename(f)
    return os.path.basename(files[0])


def transcode_to_mp4_aac(input_path: str, output_path: str) -> (bool, str):
    """
    Run ffmpeg to ensure output is MP4 with AAC audio.
    Returns (success, stderr_or_empty).
    """
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", input_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        output_path
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            return False, proc.stderr.strip()[:4000]
        return True, ""
    except Exception as e:
        return False, str(e)


def download_worker(job_id: str, url: str, typ: str, quality: str):
    """
    Blocking worker running in a thread.
    typ = 'video' or 'audio'
    """
    try:
        outtmpl = os.path.join(DOWNLOAD_DIR, f"{job_id}.%(ext)s")
        ytdl_opts = {
            "outtmpl": outtmpl,
            "no_warnings": True,
            "ignoreerrors": False,
            "quiet": False,  # set True to suppress logs
            "prefer_ffmpeg": True,
        }

        if typ == "audio":
            ytdl_opts.update({
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            })
        else:
            # video: prefer mp4/m4a combo when possible, otherwise fallback to bestvideo+bestaudio
            if quality and quality.isdigit():
                q = int(quality)
                fmt_pref = f"bestvideo[ext=mp4][height<={q}]+bestaudio[ext=m4a]/bestvideo[height<={q}]+bestaudio"
            else:
                fmt_pref = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio"
            ytdl_opts.update({
                "format": fmt_pref,
                "merge_output_format": "mp4",  # try merging into mp4
            })

        # run yt-dlp (blocking)
        with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
            ydl.download([url])

        filename = find_downloaded_file(job_id)
        if not filename:
            with jobs_lock:
                jobs[job_id]["status"] = "failed"
                jobs[job_id]["error"] = "Download finished but output file missing"
            return

        # if video and extension is webm/mkv or audio codec likely opus, transcode to mp4+aac for Windows compatibility
        lower = filename.lower()
        if typ == "video" and (lower.endswith(".webm") or lower.endswith(".mkv")):
            input_path = os.path.join(DOWNLOAD_DIR, filename)
            output_name = f"{job_id}.mp4"
            output_path = os.path.join(DOWNLOAD_DIR, output_name)

            ok, err = transcode_to_mp4_aac(input_path, output_path)
            if not ok:
                with jobs_lock:
                    jobs[job_id]["status"] = "failed"
                    jobs[job_id]["error"] = f"ffmpeg transcode failed: {err}"
                return

            # remove original if transcode ok
            try:
                os.remove(input_path)
            except Exception:
                pass

            filename = output_name

        # mark done
        with jobs_lock:
            jobs[job_id]["status"] = "done"
            jobs[job_id]["filename"] = filename

    except Exception as e:
        with jobs_lock:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = str(e)


@app.post("/download")
async def start_download(
    url: str = Form(...),
    quality: str = Form("best"),
):
    """
    Start a video download job. FormData: url, quality.
    Returns job_id. Poll /status/{job_id}.
    """
    job_id = str(uuid.uuid4())
    with jobs_lock:
        jobs[job_id] = {"status": "processing"}

    executor.submit(download_worker, job_id, url, "video", quality)
    return JSONResponse({"job_id": job_id})


@app.post("/download-audio")
async def start_download_audio(
    url: str = Form(...),
):
    job_id = str(uuid.uuid4())
    with jobs_lock:
        jobs[job_id] = {"status": "processing"}

    executor.submit(download_worker, job_id, url, "audio", "best")
    return JSONResponse({"job_id": job_id})


@app.get("/status/{job_id}")
async def job_status(job_id: str):
    with jobs_lock:
        if job_id not in jobs:
            raise HTTPException(status_code=404, detail="Job not found")
        info = jobs[job_id].copy()

    if info["status"] == "processing":
        return {"status": "processing"}
    elif info["status"] == "failed":
        return {"status": "failed", "error": info.get("error", "unknown")}
    else:
        filename = info.get("filename")
        if not filename:
            raise HTTPException(status_code=500, detail="Missing filename")
        return {"status": "done", "download_url": f"/downloads/{filename}"}


@app.get("/downloads/{filename}")
async def serve_file(filename: str):
    safe_path = os.path.join(DOWNLOAD_DIR, filename)
    if not os.path.exists(safe_path):
        raise HTTPException(status_code=404, detail="File not found")
    mime_type, _ = mimetypes.guess_type(filename)
    if not mime_type:
        mime_type = "application/octet-stream"
    return FileResponse(safe_path, media_type=mime_type, filename=filename)
