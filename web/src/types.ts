export interface JobProgress {
  scenes_count: number;
  images_ready: number;
  audio_ready: number;
  film_ready: boolean;
  youtube_published?: boolean;
  youtube_video_id?: string | null;
  youtube_video_url?: string | null;
  youtube_uploaded_at?: string | null;
}

export interface JobSummary {
  id: string;
  title: string;
  language: string;
  voice_id: string;
  style_id?: string;
  image_model?: string;
  progress: JobProgress;
  updated_at?: string;
}

export interface JobDetail {
  id: string;
  title: string;
  config: Record<string, any>;
  visual_anchors?: string | null;
  has_script: boolean;
  script_content?: string | null;
  has_film: boolean;
  film_url?: string | null;
  preview_html_url?: string | null;
  custom_prompt?: string | null;
  outline?: string | null;
}

export interface SceneStatus {
  has_image: boolean;
  has_audio: boolean;
  has_pip?: boolean;
  image_url: string | null;
  audio_url: string | null;
  pip_url?: string | null;
  duration: number;
}

export interface ScenePipConfig {
  enabled: boolean;
  image?: string;
  position: string;
  mode?: "pip" | "spotlight";
  scale: number;
  border: number;
  query?: string;
  source_title?: string;
  source_url?: string;
  fetch_error?: string | null;
}

export interface SceneSummary {
  id: string;
  index: number;
  title: string;
  narration: string;
  pip_query?: string | null;
  has_pip?: boolean;
  pip_enabled?: boolean;
  pip_mode?: "pip" | "spotlight";
  pip_error?: string | null;
  status: SceneStatus;
}

export interface SceneDetail {
  id: string;
  index: number;
  title: string;
  narration: string;
  image_prompt: string;
  image_negative?: string;
  locks: { speech: boolean; image: boolean };
  current: Record<string, string | null>;
  pip: ScenePipConfig;
  pip_mode?: "pip" | "spotlight";
  status: SceneStatus;
}

export interface AssetStyle {
  id: string;
  name: string;
  description: string;
  tags: string[];
  prefix: string;
  negative?: string;
  preview_url?: string;
}

export interface AssetTone {
  id: string;
  title: string;
  summary: string;
  content: string;
  tags?: string[];
  recommended_voice_instruct?: string;
}

export interface AssetVoice {
  id: string;
  name: string;
  language: string;
  gender: string;
  mode?: string;
  speed?: number;
  position_temperature?: number;
  steps?: number;
  reference_text?: string;
  audio_sample_url?: string;
  test_audio_url?: string;
}

export interface AiModelOption {
  id: string;
  name: string;
  badge: string;
  tag: string;
}

export const AI_TEXT_MODELS: AiModelOption[] = [
  { id: "gemini-3.8-flash", name: "Gemini 3.8 Flash", badge: "3.8 Flash", tag: "極速高擬真・首選" },
  { id: "gemini-3.5-flash", name: "Gemini 3.5 Flash", badge: "3.5 Flash", tag: "經典平衡・推薦" },
  { id: "gemini-2.5-flash", name: "Gemini 2.5 Flash", badge: "2.5 Flash", tag: "主流穩定" },
  { id: "gemini-2.0-flash", name: "Gemini 2.0 Flash", badge: "2.0 Flash", tag: "備用核心" },
];

export const AI_IMAGE_MODELS: AiModelOption[] = [
  { id: "gemini-3.1-flash-image", name: "Gemini 3.1 Flash Image", badge: "3.1 Flash", tag: "極速生圖・預設推薦" },
  { id: "gemini-3-pro-image", name: "Gemini 3 Pro Image", badge: "3 Pro", tag: "電影級旗艦・頂級畫質" },
  { id: "gemini-3.1-flash-lite-image", name: "Gemini 3.1 Flash Lite Image", badge: "3.1 Lite", tag: "輕量生圖" },
  { id: "gemini-2.5-flash-image", name: "Gemini 2.5 Flash Image", badge: "2.5 Flash", tag: "舊版相容" },
  { id: "imagen-3.0-generate-002", name: "Imagen 3 (002)", badge: "Imagen 3", tag: "專業生圖" },
];

export interface CharacterAnchor {
  id: string;
  name: string;
  appearance: string;
  has_image?: boolean;
  image_url?: string | null;
}

export interface JobVisualAnchors {
  subject: string;
  environment: string;
  use_image_reference: boolean;
  has_hero_image: boolean;
  hero_image_url?: string | null;
  characters: CharacterAnchor[];
}

export interface AnalyzeAnchorsResponse {
  subject_anchor: string;
  environment_anchor: string;
  characters: CharacterAnchor[];
}

export type NavTab = "overview" | "script" | "storyboard" | "film" | "assets" | "settings";

export interface YouTubeChannelInfo {
  id?: string;
  title?: string;
  custom_url?: string;
  thumbnail?: string;
}

export interface YouTubeAuthStatus {
  has_client_secret: boolean;
  client_secret_path?: string | null;
  is_authenticated: boolean;
  channel?: YouTubeChannelInfo | null;
  token_path?: string | null;
}

export interface YouTubePrepareData {
  job_id: string;
  has_film: boolean;
  has_srt: boolean;
  has_thumbnail: boolean;
  thumbnail_url?: string | null;
  default_title: string;
  default_description: string;
  default_tags: string[];
  default_privacy: "private" | "unlisted" | "public";
  candidate_titles?: string[];
  existing_youtube?: {
    video_id: string;
    video_url: string;
    studio_url: string;
    title: string;
    privacy_status: string;
    has_subtitles: boolean;
    has_thumbnail: boolean;
    thumbnail_error?: string | null;
    uploaded_at?: string;
  } | null;
}

export interface YouTubeOptimizeResponse {
  titles: string[];
  best_title: string;
  description: string;
  tags: string[];
  thumbnail_prompt: string;
}

export interface YouTubeGenerateThumbnailResponse {
  success: boolean;
  thumbnail_url: string;
  prompt: string;
  model?: string | null;
}

export interface YouTubeUploadPayload {
  job_id: string;
  title: string;
  description: string;
  tags: string[];
  privacy_status: "private" | "unlisted" | "public";
  upload_subtitles: boolean;
  upload_thumbnail: boolean;
  old_video_id?: string | null;
  old_video_action?: "private" | "delete" | "keep";
}

export interface YouTubeUploadStatus {
  is_uploading: boolean;
  progress: number;
  message: string;
  error?: string | null;
  result?: {
    video_id: string;
    video_url: string;
    studio_url: string;
    title: string;
    privacy_status: string;
    has_subtitles: boolean;
    has_thumbnail: boolean;
  } | null;
}

