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
    lines_per_scene: int = Field(default=2, ge=1, le=5)


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
    reference_text: Optional[str] = None
    audio_sample_url: Optional[str] = None


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
