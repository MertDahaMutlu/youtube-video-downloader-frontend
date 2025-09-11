# Online YouTube Video Downloader

A simple web-based YouTube video downloader built with **Python (FastAPI)** for the backend and **HTML/JS/CSS** for the frontend.

---

## 🚀 Features
- Download YouTube videos by pasting the link.
- Backend powered by **FastAPI** and **yt-dlp**.
- Frontend with a clean and simple interface.
- Supports multiple resolutions and audio extraction.
- Cross-platform (works on Windows, Linux, Mac).

---

## 📂 Project Structure
```
youtube-downloader/
│── backend/
│   ├── main.py          # Backend (FastAPI server)
│   └── requirements.txt # Dependencies
│── frontend/
│   ├── index.html   # Frontend page
│   ├── script.js    # Client-side logic
│   └── style.css    # Styling
```

---

## ⚙️ Installation & Setup

### 1. Clone the repo
```bash
git clone https://github.com/MertDahaMutlu/online-youtube-video-downloader.git
cd online-youtube-video-downloader
```

### 2. Create a virtual environment (optional but recommended)
```bash
python -m venv venv
venv\Scripts\activate   # On Windows
source venv/bin/activate # On Linux/Mac
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the server
```bash
uvicorn main:app --reload
```

Server will start at 👉 `http://127.0.0.1:8000`

---

## 🌍 Access from other devices
If you want others on your local network to access it, run:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```
Then share your **local IP** (e.g. `http://192.168.1.25:8000`) with others.

---

## 📦 Dependencies
- [FastAPI](https://fastapi.tiangolo.com/)
- [uvicorn](https://www.uvicorn.org/)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)

Install them manually if needed:
```bash
pip install fastapi uvicorn yt-dlp
```

---

## ⚠️ Disclaimer
This project is for **educational purposes only**.  
Downloading copyrighted content without permission may violate YouTube’s Terms of Service. Use responsibly.

---
