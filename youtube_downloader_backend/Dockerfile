# Dockerfile
FROM rust:1.72-slim

# Install ffmpeg and python3-pip + yt-dlp
RUN apt-get update && \
    apt-get install -y ffmpeg python3-pip && \
    pip3 install --no-cache-dir yt-dlp && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# Build release binary
RUN cargo build --release

EXPOSE 5000

# Run binary (it reads PORT env var, default 5000)
CMD ["./target/release/youtube_downloader_backend"]
