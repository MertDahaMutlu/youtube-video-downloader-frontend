use actix_files::NamedFile;
use actix_web::{get, web, App, HttpServer, Responder, Result};
use serde::Deserialize;
use std::path::PathBuf;
use std::process::Command;
use std::time::Duration;
use std::{fs, thread};
use uuid::Uuid;
use actix_web::http::header::{ContentDisposition, DispositionParam, DispositionType};

#[derive(Deserialize)]
struct DownloadQuery {
    url: String,
    #[serde(default = "default_type")]
    r#type: String, // "video" or "audio"
    #[serde(default = "default_quality")]
    quality: String, // "144","360","720","best"
}

fn default_type() -> String {
    "video".into()
}
fn default_quality() -> String {
    "best".into()
}

#[get("/")]
async fn home() -> impl Responder {
    web::Json(serde_json::json!({"status":"ok","message":"YouTube Downloader API running"}))
}

#[get("/download")]
async fn download(q: web::Query<DownloadQuery>) -> Result<NamedFile> {
    let url = q.url.clone();
    if url.is_empty() {
        return Err(actix_web::error::ErrorBadRequest("Missing url"));
    }
    let dtype = q.r#type.to_lowercase();
    let quality = q.quality.clone();

    // Run blocking yt-dlp work in a blocking task so async runtime isn't blocked
    let res = tokio::task::spawn_blocking(move || {
        // create temp dir
        let id = Uuid::new_v4().to_string();
        let temp_dir = PathBuf::from(format!("downloads/{}", id));
        fs::create_dir_all(&temp_dir).map_err(|e| format!("mkdir failed: {}", e))?;

        // output template: downloads/<id>/%(title)s.%(ext)s
        let outtmpl = temp_dir.join("%(title)s.%(ext)s");
        let outtmpl_str = outtmpl.to_string_lossy().to_string();

        // build format string for video
        let format_str = if dtype == "audio" {
            // audio: prefer m4a/aac then convert to mp3 via yt-dlp extract-audio
            "bestaudio[ext=m4a]/bestaudio/best".to_string()
        } else {
            match quality.as_str() {
                "144" | "240" | "360" | "480" | "720" | "1080" => {
                    format!("bestvideo[height<={0}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={0}]+bestaudio/best", quality)
                }
                _ => "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best".to_string(),
            }
        };

        // build yt-dlp args
        let mut args: Vec<String> = vec![
            "-o".into(),
            outtmpl_str,
            "--no-warnings".into(),
            "--no-playlist".into(),
            url.clone(),
        ];

        if dtype == "audio" {
            // extract audio to mp3
            // order: --extract-audio --audio-format mp3 --audio-quality 128K -o <outtmpl> <url>
            args.insert(0, "--audio-quality".into());
            args.insert(1, "128K".into());
            args.insert(2, "--audio-format".into());
            args.insert(3, "mp3".into());
            args.insert(4, "--extract-audio".into());
            args.insert(5, "--format".into());
            args.insert(6, "bestaudio".into());
        } else {
            // video: use format + merge_output_format mp4
            args.insert(0, "--merge-output-format".into());
            args.insert(1, "mp4".into());
            args.insert(2, "--format".into());
            args.insert(3, format_str);
        }

        // run yt-dlp
        let output = Command::new("yt-dlp")
            .args(&args)
            .output()
            .map_err(|e| format!("failed to run yt-dlp: {}", e))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(format!("yt-dlp failed: {}", stderr));
        }

        // find downloaded file (exclude .part)
        let mut files: Vec<PathBuf> = fs::read_dir(&temp_dir)
            .map_err(|e| format!("read_dir failed: {}", e))?
            .filter_map(|e| e.ok().map(|d| d.path()))
            .filter(|p| {
                if let Some(ext) = p.extension().and_then(|s| s.to_str()) {
                    !ext.eq_ignore_ascii_case("part")
                } else {
                    true
                }
            })
            .collect();

        files.sort();
        if files.is_empty() {
            return Err("No output file found".to_string());
        }
        let file_path = files.remove(0);

        // schedule deletion after 40s
        let temp_dir_clone = temp_dir.clone();
        let file_path_clone = file_path.clone();
        thread::spawn(move || {
            thread::sleep(Duration::from_secs(40));
            let _ = fs::remove_file(&file_path_clone);
            let _ = fs::remove_dir_all(&temp_dir_clone);
        });

        Ok(file_path)
    })
    .await
    .map_err(|e| actix_web::error::ErrorInternalServerError(format!("Join error: {}", e)))?;

    let file_path = match res {
        Ok(p) => p,
        Err(e) => return Err(actix_web::error::ErrorInternalServerError(e)),
    };

    // return file as attachment
    let mut named = NamedFile::open(&file_path)?;
    let filename = file_path
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or("download");
    let cd = ContentDisposition {
        disposition: DispositionType::Attachment,
        parameters: vec![DispositionParam::Filename(filename.into())],
    };
    named = named.set_content_disposition(cd);
    Ok(named)
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    // ensure downloads directory exists
    let _ = fs::create_dir_all("downloads");
    let port: u16 = std::env::var("PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(5000);
    println!("Listening on 0.0.0.0:{}", port);
    HttpServer::new(|| App::new().service(home).service(download))
        .bind(("0.0.0.0", port))?
        .run()
        .await
}
