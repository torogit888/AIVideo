export interface JobProgress {
  scenes_count: number;
  images_ready: number;
  audio_ready: number;
  film_ready: boolean;
}

export interface JobSummary {
  id: string;
  title: string;
  language: string;
  voice_id: string;
  style_id?: string;
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
