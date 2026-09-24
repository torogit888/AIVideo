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


class JobSummary(BaseModel):
    id: str
    title: str
    language: str = "zh-Hant"
    voice_id: str = "female01"
    style_id: Optional[str] = None
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


class CreateJobRequest(BaseModel):
    topic: str
    slug: Optional[str] = None
    script: str
    tone_id: Optional[str] = None
    voice_id: str = "female01"
    style_id: str = "future_workplace"
    visual_pacing: str = Field(default="balanced", description="視覺換鏡節奏: fast, balanced, slow")
    lines_per_scene: Optional[int] = Field(default=None, ge=1, le=5)


class UpdateJobRequest(BaseModel):
    title: Optional[str] = None
    voice_id: Optional[str] = None
    style_id: Optional[str] = None


# ==========================================
# 分鏡 (Scene)
# ==========================================
class SceneStatus(BaseModel):
    has_image: bool = False
    has_audio: bool = False
    image_url: Optional[str] = None
    audio_url: Optional[str] = None
    duration: float = 0.0


class ScenePipConfig(BaseModel):
    enabled: bool = False
    image: Optional[str] = None
    position: str = "top-right"
    scale: float = 0.35
    border: int = 8
    query: Optional[str] = None
    source_title: Optional[str] = None
    source_url: Optional[str] = None


class SceneSummary(BaseModel):
    id: str
    index: int
    title: str
    narration: str
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


# ==========================================
# 腳本生成
# ==========================================
class GenerateScriptRequest(BaseModel):
    topic: str
    tone_id: str = "tech_business_deepdive"
    word_count: int = Field(default=1500, ge=300, le=5000)
    internet_search: bool = True
    model: Optional[str] = Field("gemini-3.8-flash", description="指定 Vertex AI 文本生成模型")


class GenerateScriptResponse(BaseModel):
    script: str
    word_count: int
    estimated_scenes: int
    estimated_seconds: int


# ==========================================
# 流水線 (Pipeline)
# ==========================================
class PipelineRunRequest(BaseModel):
    job_id: str
    action: str = Field(..., description="images | tts | compose | all")
    force: bool = False
    only_missing: bool = True
    scene_id: Optional[str] = None


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
