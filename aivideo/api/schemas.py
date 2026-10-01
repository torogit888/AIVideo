from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ==========================================
# 系統與連線
# ==========================================
class SystemStatusResponse(BaseModel):
    gemini_configured: bool
    comfyui_url: str
    comfyui_online: bool
    repo_root: str


# ==========================================
# 專案 (Job)
# ==========================================
class JobProgress(BaseModel):
    scenes_count: int = 0
    images_ready: int = 0
    audio_ready: int = 0
    film_ready: bool = False
    youtube_published: bool = False
    youtube_video_id: Optional[str] = None
    youtube_video_url: Optional[str] = None
    youtube_uploaded_at: Optional[str] = None


class JobSummary(BaseModel):
    id: str
    title: str
    language: str = "zh-Hant"
    voice_id: str = "female01"
    style_id: Optional[str] = None
    image_model: Optional[str] = None
    progress: JobProgress
    updated_at: Optional[str] = None


class JobDetail(BaseModel):
    id: str
    title: str
    config: Dict[str, Any]
    visual_anchors: Optional[str] = None
    has_script: bool = False
    script_content: Optional[str] = None
    has_film: bool = False
    film_url: Optional[str] = None
    preview_html_url: Optional[str] = None
    custom_prompt: Optional[str] = None
    outline: Optional[str] = None


class CharacterAnchorInput(BaseModel):
    id: Optional[str] = None
    name: str
    appearance: str = ""


class CreateJobRequest(BaseModel):
    topic: str
    slug: Optional[str] = None
    script: str
    tone_id: Optional[str] = None
    voice_id: str = "female01"
    style_id: str = "future_workplace"
    image_model: Optional[str] = Field(default="gemini-3.1-flash-image", description="生圖模型")
    visual_pacing: str = Field(default="balanced", description="視覺換鏡節奏: fast, balanced, slow")
    lines_per_scene: Optional[int] = Field(default=None, ge=1, le=5)
    subject_anchor: Optional[str] = Field(default=None, description="主體外觀特徵錨點（多人時為彙總字串）")
    environment_anchor: Optional[str] = Field(default=None, description="環境與光影基調錨點")
    characters: Optional[List[CharacterAnchorInput]] = Field(default=None, description="每人獨立外觀錨點")
    custom_prompt: Optional[str] = Field(default=None, description="指定 Prompt 與故事特定要求")
    outline: Optional[str] = Field(default=None, description="6 幕故事大綱")


class UpdateJobRequest(BaseModel):
    title: Optional[str] = None
    voice_id: Optional[str] = None
    style_id: Optional[str] = None
    image_model: Optional[str] = None
    custom_prompt: Optional[str] = None


# ==========================================
# YouTube 發布
# ==========================================
class YouTubeChannelInfo(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    custom_url: Optional[str] = None
    thumbnail: Optional[str] = None


class YouTubeAuthStatusResponse(BaseModel):
    has_client_secret: bool
    client_secret_path: Optional[str] = None
    is_authenticated: bool
    channel: Optional[YouTubeChannelInfo] = None
    token_path: Optional[str] = None


class YouTubePrepareResponse(BaseModel):
    job_id: str
    has_film: bool
    has_srt: bool
    has_thumbnail: bool
    thumbnail_url: Optional[str] = None
    default_title: str
    default_description: str
    default_tags: List[str]
    default_privacy: str = "unlisted"
    candidate_titles: List[str] = Field(default_factory=list)
    existing_youtube: Optional[Dict[str, Any]] = None


class YouTubeSaveMetadataRequest(BaseModel):
    job_id: str
    title: str
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    privacy_status: Optional[str] = "unlisted"
    candidate_titles: Optional[List[str]] = None


class YouTubeUpdateExistingRequest(BaseModel):
    job_id: str
    video_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    privacy_status: Optional[str] = None
    upload_thumbnail: bool = True


class YouTubeOptimizeRequest(BaseModel):
    job_id: str


class YouTubeOptimizeResponse(BaseModel):
    titles: List[str]
    best_title: str
    description: str
    tags: List[str]
    thumbnail_prompt: str


class YouTubeGenerateThumbnailRequest(BaseModel):
    job_id: str
    title: Optional[str] = None
    prompt: Optional[str] = None


class YouTubeGenerateThumbnailResponse(BaseModel):
    success: bool
    thumbnail_url: str
    prompt: str
    model: Optional[str] = None


class YouTubeUploadRequest(BaseModel):
    job_id: str
    title: str
    description: str = ""
    tags: List[str] = Field(default_factory=lambda: ["AIVideo", "說書人", "紀錄片"])
    privacy_status: str = Field(default="unlisted", description="private, unlisted, public")
    upload_subtitles: bool = True
    upload_thumbnail: bool = True
    old_video_id: Optional[str] = None
    old_video_action: str = Field(default="private", description="private, delete, keep")


class YouTubeUploadStatusResponse(BaseModel):
    is_uploading: bool
    progress: float = 0.0
    message: str = ""
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None

    outline: Optional[str] = None
    tone_id: Optional[str] = None
    script: Optional[str] = None


# ==========================================
# 視覺一致性與定裝參考 (Visual Continuity)
# ==========================================
class AnalyzeAnchorsRequest(BaseModel):
    topic: str
    script: str
    style_id: Optional[str] = Field(default=None, description="專案選擇的生圖風格，分析時鎖定畫風")


class CharacterAnchorDraft(BaseModel):
    id: str
    name: str
    appearance: str = ""


class AnalyzeAnchorsResponse(BaseModel):
    subject_anchor: str
    environment_anchor: str
    characters: List[CharacterAnchorDraft] = Field(default_factory=list)


class CharacterAnchor(BaseModel):
    id: str
    name: str
    appearance: str = ""
    has_image: bool = False
    image_url: Optional[str] = None


class JobVisualAnchorsResponse(BaseModel):
    subject: str = ""
    environment: str = ""
    use_image_reference: bool = True
    has_hero_image: bool = False
    hero_image_url: Optional[str] = None
    characters: List[CharacterAnchor] = Field(default_factory=list)


class UpdateVisualAnchorsRequest(BaseModel):
    subject: Optional[str] = None
    environment: Optional[str] = None
    use_image_reference: Optional[bool] = None
    characters: Optional[List[CharacterAnchorInput]] = None


class AddCharacterRequest(BaseModel):
    name: str
    appearance: str = ""


class PatchCharacterRequest(BaseModel):
    name: Optional[str] = None
    appearance: Optional[str] = None


class GenerateHeroAnchorResponse(BaseModel):
    success: bool
    message: str
    hero_image_url: str = ""
    generated_count: int = 0


# ==========================================
# 分鏡 (Scene)
# ==========================================
class SceneStatus(BaseModel):
    has_image: bool = False
    has_audio: bool = False
    has_pip: bool = False
    image_url: Optional[str] = None
    audio_url: Optional[str] = None
    pip_url: Optional[str] = None
    duration: float = 0.0


class ScenePipConfig(BaseModel):
    enabled: bool = False
    image: Optional[str] = None
    position: str = "right-center"
    mode: str = "pip"
    scale: float = 0.24
    border: int = 5
    query: Optional[str] = None
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    fetch_error: Optional[str] = None


class SceneSummary(BaseModel):
    id: str
    index: int
    title: str
    narration: str
    pip_query: Optional[str] = None
    has_pip: bool = False
    pip_enabled: bool = False
    pip_mode: str = "pip"
    pip_error: Optional[str] = None
    status: SceneStatus


class SceneDetail(BaseModel):
    id: str
    index: int
    title: str
    narration: str
    image_prompt: str
    image_negative: Optional[str] = ""
    locks: Dict[str, bool] = Field(default_factory=lambda: {"speech": False, "image": False})
    current: Dict[str, Optional[str]] = Field(default_factory=dict)
    pip: ScenePipConfig = Field(default_factory=ScenePipConfig)
    status: SceneStatus


class ScenePatchRequest(BaseModel):
    title: Optional[str] = None
    narration: Optional[str] = None
    image_prompt: Optional[str] = None
    image_negative: Optional[str] = None
    locks: Optional[Dict[str, bool]] = None
    pip: Optional[ScenePipConfig] = None


class FetchScenePipRequest(BaseModel):
    query: Optional[str] = None


# ==========================================
# 腳本與大綱生成
# ==========================================
class GenerateOutlineRequest(BaseModel):
    topic: str
    tone_id: str = "michelin_curious"
    model: Optional[str] = Field("gemini-3.8-flash", description="指定 Vertex AI 文本生成模型")
    user_prompt: Optional[str] = Field(default=None, description="使用者先輸入的基本提示詞或靈感要求")


class GenerateOutlineResponse(BaseModel):
    outline: str


class GenerateScriptRequest(BaseModel):
    topic: str
    tone_id: str = "michelin_curious"
    word_count: int = Field(default=1500, ge=300, le=5000)
    internet_search: bool = True
    model: Optional[str] = Field("gemini-3.8-flash", description="指定 Vertex AI 文本生成模型")
    notes: Optional[str] = Field(default=None, description="故事核心看點或大綱備忘")
    user_prompt: Optional[str] = Field(default=None, description="使用者獨立的指定 Prompt / 核心要求")


class GenerateScriptResponse(BaseModel):
    script: str
    word_count: int
    estimated_scenes: int
    estimated_seconds: int


class ExpandScriptRequest(BaseModel):
    script: str
    topic: Optional[str] = ""
    tone_id: str = "michelin_curious"
    target_word_count: int = Field(default=3500, ge=500, le=5000)
    model: Optional[str] = Field("gemini-3.8-flash", description="指定 Vertex AI 文本生成模型")


# ==========================================
# 流水線 (Pipeline)
# ==========================================
class PipelineRunRequest(BaseModel):
    job_id: str
    action: str = Field(..., description="images | tts | compose | all")
    force: bool = False
    only_missing: bool = True
    scene_id: Optional[str] = None
    burn_subtitles: Optional[bool] = Field(default=None, description="是否燒錄 ASS 字幕至成片畫面（None 表示依專案 job.yaml 設定，預設不燒錄）")


class PipelineStatusResponse(BaseModel):
    is_running: bool
    current_job: Optional[str] = None
    current_action: Optional[str] = None
    progress: float = 0.0
    message: str = ""
    recent_logs: List[str] = Field(default_factory=list)


# ==========================================
# 素材 (Assets)
# ==========================================
class AssetTone(BaseModel):
    id: str
    title: str
    summary: str
    content: str
    tags: List[str] = Field(default_factory=list)
    recommended_voice_instruct: Optional[str] = None


class AssetVoice(BaseModel):
    id: str
    name: str
    language: str
    gender: str
    mode: Optional[str] = "clone"
    speed: Optional[float] = 1.0
    position_temperature: Optional[float] = 0.1
    steps: Optional[int] = 32
    reference_text: Optional[str] = None
    audio_sample_url: Optional[str] = None
    test_audio_url: Optional[str] = None


class TestVoiceRequest(BaseModel):
    text: Optional[str] = "歡迎使用智能影視創作系統，這是一段測試發音人音色與位置溫度的語音合成效果。"
    speed: Optional[float] = None
    position_temperature: Optional[float] = None
    steps: Optional[int] = None
    mode: Optional[str] = None
    instruct: Optional[str] = None


class AssetStyle(BaseModel):
    id: str
    name: str
    description: str
    tags: List[str] = Field(default_factory=list)
    prefix: str
    negative: Optional[str] = None
    preview_url: Optional[str] = None


class UpdateStyleRequest(BaseModel):
    name: str
    description: str
    prefix: str
    negative: Optional[str] = ""
    tags: Optional[List[str]] = None
    preview_base64: Optional[str] = None


class CreateStyleRequest(BaseModel):
    id: str
    name: str
    description: str = ""
    prefix: str
    negative: Optional[str] = ""
    tags: Optional[List[str]] = None
    preview_base64: Optional[str] = None


class CreateToneRequest(BaseModel):
    id: str
    title: str
    summary: str = ""
    tags: List[str] = Field(default_factory=list)
    recommended_voice_instruct: Optional[str] = None
    content: str


class ExtractToneRequest(BaseModel):
    text: str = Field(..., description="參考口白、文章或逐字稿文本")
    tone_id: Optional[str] = Field(None, description="指定或覆蓋的口吻 ID（選填）")
    auto_save: bool = Field(True, description="是否由 Vertex AI 直接寫入 assets/tones/<id>.md 專案檔案")
    model: Optional[str] = Field("gemini-3.8-flash", description="指定 Vertex AI 文本分析模型")
    title: Optional[str] = Field(None, description="指定口吻中文名稱（若為空則由 Vertex AI 產生）")


class UpdateToneRequest(BaseModel):
    title: str
    summary: str = ""
    tags: List[str] = Field(default_factory=list)
    recommended_voice_instruct: Optional[str] = None
    content: str


class CreateVoiceRequest(BaseModel):
    id: str
    name: str
    gender: str = "女性"
    mode: str = "clone"
    speed: float = 1.0
    position_temperature: float = 0.1
    steps: int = 32
    reference_text: str = ""
    audio_base64: Optional[str] = None


class UpdateVoiceRequest(BaseModel):
    name: str
    gender: str = "女性"
    mode: str = "clone"
    speed: float = 1.0
    position_temperature: float = 0.1
    steps: int = 32
    reference_text: str = ""
    audio_base64: Optional[str] = None
