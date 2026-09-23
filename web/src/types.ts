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

export interface SceneStatus {
  has_image: boolean;
  has_audio: boolean;
  image_url: string | null;
  audio_url: string | null;
  duration: number;
}

export interface ScenePipConfig {
  enabled: boolean;
  image?: string;
  position: string;
  scale: number;
  border: number;
  query?: string;
  source_title?: string;
  source_url?: string;
}

export interface SceneSummary {
  id: string;
  index: number;
  title: string;
  narration: string;
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
  reference_text?: string;
  audio_sample_url?: string;
}

export type NavTab = "overview" | "script" | "storyboard" | "film" | "assets" | "settings";
