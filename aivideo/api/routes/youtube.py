from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from fastapi.responses import HTMLResponse

from aivideo.api.schemas import (
    YouTubeAuthStatusResponse,
    YouTubeGenerateThumbnailRequest,
    YouTubeGenerateThumbnailResponse,
    YouTubeOptimizeRequest,
    YouTubeOptimizeResponse,
    YouTubePrepareResponse,
    YouTubeSaveMetadataRequest,
    YouTubeUpdateExistingRequest,
    YouTubeUploadRequest,
    YouTubeUploadStatusResponse,
)
from aivideo.youtube_uploader import (
    exchange_code_for_token,
    generate_youtube_chapters,
    generate_youtube_metadata,
    generate_youtube_thumbnail,
    get_auth_status,
    get_authorization_url,
    get_job_youtube_info,
    save_client_secret_content,
    update_existing_youtube_video,
    upload_video_to_youtube,
)

router = APIRouter(prefix="/youtube", tags=["YouTube 成片發布"])
REPO_ROOT = Path(__file__).resolve().parents[3]
JOBS_DIR = REPO_ROOT / "jobs"


class YouTubeUploadTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self.is_uploading = False
        self.progress = 0.0
        self.message = ""
        self.error: Optional[str] = None
        self.result: Optional[Dict[str, Any]] = None

    def start(self):
        with self._lock:
            self.is_uploading = True
            self.progress = 0.01
            self.message = "正在初始化 YouTube 上傳連線..."
            self.error = None
            self.result = None

    def update(self, progress: float, message: str):
        with self._lock:
            self.progress = progress
            self.message = message

    def finish(self, result: Dict[str, Any]):
        with self._lock:
            self.is_uploading = False
            self.progress = 1.0
            self.message = "發布完成！"
            self.result = result

    def fail(self, error: str):
        with self._lock:
            self.is_uploading = False
            self.error = error
            self.message = f"上傳失敗：{error}"

    def get_status(self) -> YouTubeUploadStatusResponse:
        with self._lock:
            return YouTubeUploadStatusResponse(
                is_uploading=self.is_uploading,
                progress=self.progress,
                message=self.message,
                error=self.error,
                result=self.result,
            )


tracker = YouTubeUploadTracker()


@router.get("/status", response_model=YouTubeAuthStatusResponse)
def get_status():
    """取得 YouTube 授權狀態與當前登入的頻道資訊。"""
    try:
        return get_auth_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auth/secret")
async def upload_secret(req: Request):
    """上傳或匯入 Google OAuth 用戶端 client_secret.json 內容。"""
    try:
        data = await req.json()
        content = data.get("content") if isinstance(data, dict) else str(data)
        if not content:
            raise HTTPException(status_code=400, detail="請提供 client_secret 內容")
        save_client_secret_content(content)
        return {"status": "ok", "message": "成功儲存 client_secret.json"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"憑證解析失敗：{e}")


@router.get("/auth/url")
def get_auth_url(redirect_uri: Optional[str] = None):
    """取得 Google OAuth 授權登入 URL。"""
    try:
        url = get_authorization_url(redirect_uri)
        return {"auth_url": url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/auth/callback", response_class=HTMLResponse)
def auth_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    """接收 Google OAuth 瀏覽器重定向回調，自動完成換票並關閉授權視窗。"""
    if error:
        return HTMLResponse(
            f"""
            <html>
            <body style="background:#121212;color:#f87171;font-family:system-ui,sans-serif;text-align:center;padding:50px;">
                <h2>❌ Google 授權失敗</h2>
                <p>{error}</p>
                <p style="color:#888;">請關閉此視窗並重新嘗試。</p>
            </body>
            </html>
            """,
            status_code=400,
        )

    if not code:
        return HTMLResponse("<h3>未收到授權碼</h3>", status_code=400)

    try:
        exchange_code_for_token(code=code, state=state)
        return HTMLResponse(
            """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>YouTube 授權成功</title>
                <style>
                    body {
                        background: #0f0f10;
                        color: #ffffff;
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                        display: flex;
                        flex-direction: column;
                        align-items: center;
                        justify-content: center;
                        height: 100vh;
                        margin: 0;
                    }
                    .card {
                        background: #18181b;
                        border: 1px solid #27272a;
                        padding: 32px 48px;
                        border-radius: 16px;
                        text-align: center;
                        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
                    }
                    h2 { color: #4ade80; margin-bottom: 8px; }
                    p { color: #a1a1aa; font-size: 14px; margin: 4px 0; }
                </style>
            </head>
            <body>
                <div class="card">
                    <h2>🎉 YouTube 授權成功！</h2>
                    <p>已成功綁定頻道，視窗即將自動關閉。</p>
                    <p style="font-size: 12px; color: #71717a; margin-top: 16px;">請返回 AIVideo Studio 繼續發布流程...</p>
                </div>
                <script>
                    try {
                        if (window.opener) {
                            window.opener.postMessage({ type: 'YOUTUBE_AUTH_SUCCESS' }, '*');
                        }
                    } catch (e) {}
                    setTimeout(function() {
                        window.close();
                    }, 2000);
                </script>
            </body>
            </html>
            """
        )
    except Exception as e:
        return HTMLResponse(
            f"""
            <html>
            <body style="background:#121212;color:#f87171;font-family:system-ui,sans-serif;text-align:center;padding:50px;">
                <h2>❌ 授權交換失敗</h2>
                <p>{e}</p>
            </body>
            </html>
            """,
            status_code=500,
        )


@router.post("/auth/exchange")
def exchange_code(payload: Dict[str, str]):
    """使用手動貼上的授權碼完成驗證（備用手動模式）。"""
    code = payload.get("code")
    redirect_uri = payload.get("redirect_uri")
    if not code:
        raise HTTPException(status_code=400, detail="請提供授權碼 (code)")
    try:
        status = exchange_code_for_token(code.strip(), redirect_uri)
        return status
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"授權交換失敗：{e}")


@router.get("/prepare/{job_id}", response_model=YouTubePrepareResponse)
def prepare_job_upload(job_id: str):
    """為指定專案生成預設的 YouTube 發布資訊（標題、描述、時間軸章節、縮圖檢測）。"""
    job_dir = JOBS_DIR / job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="找不到指定專案")

    film_path = job_dir / "compose" / "film.mp4"
    srt_path = job_dir / "compose" / "timeline.srt"
    
    # 尋找縮圖 (優先看是否有專屬 thumbnail.png，否則看第一幕)
    has_thumb = False
    thumb_url = None
    dedicated_thumb = job_dir / "compose" / "thumbnail.png"
    if dedicated_thumb.is_file():
        has_thumb = True
        thumb_url = f"/media/jobs/{job_id}/compose/thumbnail.png"
    else:
        scenes_dir = job_dir / "scenes"
        if scenes_dir.is_dir():
            for sd in sorted(scenes_dir.iterdir()):
                if (sd / "current.png").is_file():
                    has_thumb = True
                    thumb_url = f"/media/jobs/{job_id}/scenes/{sd.name}/current.png"
                    break

    # 取得專案標題
    title = job_id
    outline_text = ""
    job_yaml = job_dir / "job.yaml"
    if job_yaml.is_file():
        try:
            import yaml
            with open(job_yaml, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data and data.get("title"):
                    title = data["title"]
        except Exception:
            pass

    outline_file = job_dir / "outline.md"
    if outline_file.is_file():
        try:
            outline_text = outline_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass

    desc_parts = []
    if outline_text:
        desc_parts.append(outline_text)
    desc_parts.append(f"#{title.split()[0] if title else '說書'} #歷史秘辛 #紀錄片")

    default_desc = "\n\n".join(desc_parts)

    tags = ["說書人", "紀錄片", title.split()[0] if title else "AI故事"]
    existing_yt = get_job_youtube_info(job_dir)

    # 優先讀取已儲存的 YouTube 中繼資料草稿
    meta_file = job_dir / "compose" / "youtube_metadata.json"
    saved_meta: Dict[str, Any] = {}
    if meta_file.is_file():
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                saved_meta = json.load(f)
        except Exception:
            pass

    final_title = saved_meta.get("title") or (existing_yt.get("title") if existing_yt else None) or title
    final_desc = saved_meta.get("description") or default_desc
    final_tags = saved_meta.get("tags") or (existing_yt.get("tags") if existing_yt else None) or tags
    final_privacy = saved_meta.get("privacy_status") or (existing_yt.get("privacy_status") if existing_yt else None) or "unlisted"
    candidate_titles = saved_meta.get("candidate_titles") or []

    return YouTubePrepareResponse(
        job_id=job_id,
        has_film=film_path.is_file(),
        has_srt=srt_path.is_file(),
        has_thumbnail=has_thumb,
        thumbnail_url=thumb_url,
        default_title=final_title,
        default_description=final_desc,
        default_tags=final_tags,
        default_privacy=final_privacy,
        candidate_titles=candidate_titles,
        existing_youtube=existing_yt,
    )


@router.post("/metadata")
def save_youtube_metadata(req: YouTubeSaveMetadataRequest):
    """保存或手動更新專案的 YouTube 中繼資料草稿（標題、候選標題、說明欄、標籤、隱私設定）。"""
    job_dir = JOBS_DIR / req.job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="找不到指定專案")

    meta_file = job_dir / "compose" / "youtube_metadata.json"
    existing_meta: Dict[str, Any] = {}
    if meta_file.is_file():
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                existing_meta = json.load(f)
        except Exception:
            pass

    existing_meta.update({
        "title": req.title,
        "description": req.description,
        "tags": req.tags,
        "privacy_status": req.privacy_status,
    })
    if req.candidate_titles:
        existing_meta["candidate_titles"] = req.candidate_titles

    dest_dir = job_dir / "compose"
    dest_dir.mkdir(parents=True, exist_ok=True)
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(existing_meta, f, indent=2, ensure_ascii=False)

    return {"status": "ok", "message": "已成功儲存 YouTube 中繼資料草稿"}


@router.post("/update-existing")
def update_existing_video(req: YouTubeUpdateExistingRequest):
    """更新現有 YouTube 影片的資訊（例如補傳縮圖、修改標題/說明），無須重新上傳影片。"""
    job_dir = JOBS_DIR / req.job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="找不到指定專案")

    existing_yt = get_job_youtube_info(job_dir)
    target_id = req.video_id or (existing_yt.get("video_id") if existing_yt else None)
    if not target_id:
        raise HTTPException(status_code=400, detail="找不到該專案關聯的 YouTube 影片 ID")

    try:
        updated = update_existing_youtube_video(
            job_dir=job_dir,
            video_id=target_id,
            title=req.title,
            description=req.description,
            tags=req.tags,
            privacy_status=req.privacy_status,
            upload_thumbnail=req.upload_thumbnail,
        )
        return updated
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新現有影片失敗：{e}")


@router.post("/optimize-metadata", response_model=YouTubeOptimizeResponse)
def optimize_metadata(req: YouTubeOptimizeRequest):
    """利用 Gemini 深度分析故事，產出符合 YouTube 演算法推薦的標題候選、說明欄、標籤與縮圖提示詞。"""
    job_dir = JOBS_DIR / req.job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="找不到指定專案")
    try:
        data = generate_youtube_metadata(job_dir)
        # 自動存檔至 compose/youtube_metadata.json
        meta_to_save = {
            "title": data.get("best_title") or (data.get("titles") and data["titles"][0]) or "",
            "candidate_titles": data.get("titles") or [],
            "description": data.get("description") or "",
            "tags": data.get("tags") or [],
            "thumbnail_prompt": data.get("thumbnail_prompt") or "",
        }
        dest_dir = job_dir / "compose"
        dest_dir.mkdir(parents=True, exist_ok=True)
        with open(dest_dir / "youtube_metadata.json", "w", encoding="utf-8") as f:
            json.dump(meta_to_save, f, indent=2, ensure_ascii=False)
        return YouTubeOptimizeResponse(**data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 最佳化生成失敗：{e}")


@router.post("/generate-thumbnail", response_model=YouTubeGenerateThumbnailResponse)
def generate_thumbnail(req: YouTubeGenerateThumbnailRequest):
    """利用專案相同的畫風與角色定裝圖，由 Gemini 生成 16:9 高張力 YouTube 官方封面圖。"""
    job_dir = JOBS_DIR / req.job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="找不到指定專案")
    try:
        res = generate_youtube_thumbnail(job_dir, title=req.title, custom_prompt=req.prompt)
        return YouTubeGenerateThumbnailResponse(**res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"縮圖生成失敗：{e}")


def _background_upload_task(req: YouTubeUploadRequest):
    job_dir = JOBS_DIR / req.job_id
    try:
        result = upload_video_to_youtube(
            job_dir=job_dir,
            title=req.title,
            description=req.description,
            tags=req.tags,
            privacy_status=req.privacy_status,
            upload_subtitles=req.upload_subtitles,
            upload_thumbnail=req.upload_thumbnail,
            old_video_id=req.old_video_id,
            old_video_action=req.old_video_action,
            progress_callback=tracker.update,
        )
        tracker.finish(result)
    except Exception as e:
        tracker.fail(str(e))


@router.post("/upload")
def upload_video(req: YouTubeUploadRequest, background_tasks: BackgroundTasks):
    """啟動非同步 YouTube 影片發布任務。"""
    job_dir = JOBS_DIR / req.job_id
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="找不到指定專案")

    film_path = job_dir / "compose" / "film.mp4"
    if not film_path.is_file():
        raise HTTPException(status_code=400, detail="成片尚未合成，無法發布至 YouTube")

    auth = get_auth_status()
    if not auth.get("is_authenticated"):
        raise HTTPException(status_code=401, detail="尚未授權 Google 帳號，請先完成 YouTube 登入驗證")

    if tracker.is_uploading:
        raise HTTPException(status_code=409, detail="目前已有其他影片正在上傳中，請稍候")

    tracker.start()
    background_tasks.add_task(_background_upload_task, req)

    return {"status": "started", "job_id": req.job_id, "message": "已開始背景上傳至 YouTube"}


@router.get("/upload/status", response_model=YouTubeUploadStatusResponse)
def get_upload_status():
    """查詢當前 YouTube 影片上傳任務進度。"""
    return tracker.get_status()
