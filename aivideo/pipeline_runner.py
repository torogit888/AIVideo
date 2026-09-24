from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Callable

from aivideo.commands.compose import run_compose
from aivideo.commands.images import run_images
from aivideo.commands.preview import generate_preview_html
from aivideo.commands.tts import run_tts

REPO_ROOT = Path(__file__).resolve().parents[1]


class CmdArgs:
    """傳遞給各子命令的參數封裝，支援取消/暫停控制回調。"""

    def __init__(
        self,
        job: Path | str,
        force: bool = False,
        scene: str | None = None,
        voice_id: str | None = None,
        count: int = 1,
        draft: bool = False,
        new_seed: bool = False,
        keep_seed: bool = False,
        progress_callback: Callable[..., Any] | None = None,
        skip_existing: bool = False,
        check_control: Callable[..., bool] | None = None,
    ):
        self.job = str(job)
        self.force = force
        self.scene = scene
        self.voice_id = voice_id
        self.count = count
        self.draft = draft
        self.new_seed = new_seed
        self.keep_seed = keep_seed
        self.progress_callback = progress_callback
        self.skip_existing = skip_existing
        self.check_control = check_control


class PipelineRunner:
    """管理專案全流程與批次生成的背景執行緒控制器，支援即時暫停、繼續與中止。"""

    def __init__(self, job_name: str, job_path: Path):
        self.job_name = job_name
        self.job_path = job_path
        self.thread: threading.Thread | None = None

        # 狀態標記
        self.is_running: bool = False
        self.is_paused: bool = False
        self.is_stopped: bool = False
        self.is_done: bool = False
        self.error_msg: str | None = None

        # 進度與階段
        self.mode: str = "all"
        self.stage: str = ""
        self.progress: float = 0.0
        self.status_msg: str = ""

        # 即時預覽資訊 (提供給 Streamlit 動態繪製)
        self.live_cur: int = 0
        self.live_tot: int = 0
        self.live_phase: str = ""
        self.live_dir: Path | None = None

        # 控制事件 (pause_event set 表示正常運行，clear 表示暫停)
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    def start(
        self,
        mode: str = "all",
        skip_done: bool = True,
        auto_pip: bool = True,
        pause_between_stages: bool = False,
    ) -> bool:
        """啟動生成流程。若目前已有任務正在運行則回傳 False。"""
        with self._lock:
            if self.is_running and self.thread and self.thread.is_alive():
                return False

            self.mode = mode
            self.is_running = True
            self.is_paused = False
            self.is_stopped = False
            self.is_done = False
            self.error_msg = None
            self.progress = 0.0
            self.status_msg = "準備啟動任務..."
            self.live_cur = 0
            self.live_tot = 0
            self.live_phase = ""
            self.live_dir = None

            self._pause_event.set()
            self._stop_event.clear()

            self.thread = threading.Thread(
                target=self._run_worker,
                args=(mode, skip_done, auto_pip, pause_between_stages),
                daemon=True,
            )
            self.thread.start()
            return True

    def pause(self) -> None:
        """請求暫停執行（將在當前分鏡存檔完成後安全休眠）。"""
        with self._lock:
            if self.is_running and not self.is_paused:
                self.is_paused = True
                self._pause_event.clear()
                self.status_msg = f"⏸️ 已請求暫停（將在當前分鏡儲存完畢後暫停）"

    def resume(self) -> None:
        """喚醒執行緒，自暫停位置繼續執行。"""
        with self._lock:
            if self.is_running and self.is_paused:
                self.is_paused = False
                self._pause_event.set()
                self.status_msg = "▶️ 已恢復執行，接續處理下一幕分鏡..."

    def stop(self) -> None:
        """請求中止任務。已完成的分鏡將完整保留。"""
        with self._lock:
            if self.is_running:
                self.is_stopped = True
                self.is_paused = False
                self._stop_event.set()
                self._pause_event.set()  # 解除休眠以立即退出
                self.status_msg = "⏹️ 正在安全中止任務..."

    def reset(self) -> None:
        """重置控制器狀態。"""
        with self._lock:
            self.is_running = False
            self.is_paused = False
            self.is_stopped = False
            self.is_done = False
            self.error_msg = None
            self.progress = 0.0
            self.status_msg = ""
            self.live_dir = None

    def check_control(self, phase: str = "", s_dir: Path | None = None) -> bool:
        """供子命令調用的檢查點。若已中止回傳 True；若暫停則在此休眠直到喚醒。"""
        if self._stop_event.is_set():
            return True

        if not self._pause_event.is_set():
            with self._lock:
                self.is_paused = True
                cur_s = self.live_cur
                tot_s = self.live_tot
                p_text = f"第 {cur_s}/{tot_s} 幕" if tot_s > 0 else phase
                self.status_msg = f"⏸️ 流程已於【{p_text}】安全暫停（分鏡進度已妥善保存，可隨時點擊「繼續」）"

            # 休眠等待使用者點擊「繼續」或「中止」
            while not self._pause_event.is_set():
                if self._stop_event.is_set():
                    return True
                time.sleep(0.3)

            with self._lock:
                self.is_paused = False

        return self._stop_event.is_set()

    def _run_worker(
        self,
        mode: str,
        skip_done: bool,
        auto_pip: bool,
        pause_between_stages: bool,
    ) -> None:
        """背景線程主工作流程。"""
        try:
            # 進度回調函式
            def on_img_prog(cur: int, tot: int, msg: str, s_dir: Path | None = None) -> None:
                with self._lock:
                    self.live_cur = cur
                    self.live_tot = tot
                    self.live_phase = "出圖"
                    if s_dir:
                        self.live_dir = Path(s_dir)
                    frac = (0.30 * (cur / max(1, tot))) if mode == "all" else (cur / max(1, tot))
                    self.progress = min(1.0, max(0.0, frac))
                    self.status_msg = f"🎨 [出圖] ({cur}/{tot}) - {msg}"

            def on_pip_prog(cur: int, tot: int, msg: str, s_dir: Path | None = None) -> None:
                with self._lock:
                    self.live_cur = cur
                    self.live_tot = tot
                    self.live_phase = "Auto-PiP"
                    if s_dir:
                        self.live_dir = Path(s_dir)
                    frac = (0.30 + 0.15 * (cur / max(1, tot))) if mode == "all" else (cur / max(1, tot))
                    self.progress = min(1.0, max(0.0, frac))
                    self.status_msg = f"🌐 [考據] ({cur}/{tot}) - {msg}"

            def on_tts_prog(cur: int, tot: int, msg: str, s_dir: Path | None = None) -> None:
                with self._lock:
                    self.live_cur = cur
                    self.live_tot = tot
                    self.live_phase = "配音"
                    if s_dir:
                        self.live_dir = Path(s_dir)
                    frac = (0.45 + 0.45 * (cur / max(1, tot))) if mode == "all" else (cur / max(1, tot))
                    self.progress = min(1.0, max(0.0, frac))
                    self.status_msg = f"🎙️ [配音] ({cur}/{tot}) - {msg}"

            # ========================
            # 階段 1: 批次出圖
            # ========================
            if mode in ("all", "images"):
                self.stage = "🎨 [1/4 出圖]"
                self.status_msg = "正在呼叫 Gemini API 批次產生畫面..."
                if self.check_control(phase="出圖準備"):
                    return

                cmd_args = CmdArgs(
                    job=self.job_path,
                    force=(not skip_done),
                    skip_existing=skip_done,
                    progress_callback=on_img_prog,
                    check_control=self.check_control,
                )
                ret_img = run_images(cmd_args, progress_callback=on_img_prog)

                if self.check_control(phase="出圖完畢"):
                    return

                if ret_img != 0 and mode == "all":
                    self.pause()
                    self.status_msg = "⚠️ [1/4 出圖] 部分分鏡出圖失敗，已自動暫停。可點擊「繼續執行」補跑未完成場景，或於分鏡看板檢查。"
                    if self.check_control(phase="出圖異常檢查"):
                        return

                if mode == "all" and pause_between_stages:
                    self.pause()
                    self.status_msg = "⏸️ [1/4 出圖] 已全數完成！已自動暫停供審查畫面，確認滿意後請點擊「繼續執行」。"
                    if self.check_control(phase="出圖審查"):
                        return

            # ========================
            # 階段 2: 自動考據配圖 (Auto-PiP)
            # ========================
            if mode in ("all", "pip") and (mode == "pip" or auto_pip):
                self.stage = "🌐 [2/4 考據]"
                self.status_msg = "正在以 AI 掃描台詞向維基共享資源配對真實考據圖..."
                if self.check_control(phase="考據準備"):
                    return

                from aivideo.auto_pip import auto_fetch_and_apply_pip

                auto_fetch_and_apply_pip(
                    self.job_path,
                    progress_callback=on_pip_prog,
                    check_control=self.check_control,
                )

                if self.check_control(phase="考據完畢"):
                    return

            # ========================
            # 階段 3: 批次語音合成
            # ========================
            if mode in ("all", "tts"):
                self.stage = "🎙️ [3/4 配音]"
                self.status_msg = "正在透過 ComfyUI 逐句進行聲音克隆合成..."
                if self.check_control(phase="配音準備"):
                    return

                cmd_args = CmdArgs(
                    job=self.job_path,
                    force=(not skip_done),
                    skip_existing=skip_done,
                    progress_callback=on_tts_prog,
                    check_control=self.check_control,
                )
                ret_tts = run_tts(cmd_args, progress_callback=on_tts_prog)

                if self.check_control(phase="配音完畢"):
                    return

                if ret_tts != 0 and mode == "all":
                    self.pause()
                    self.status_msg = "⚠️ [3/4 配音] 部分分鏡配音失敗，已自動暫停。可點擊「繼續執行」重試未完成語音。"
                    if self.check_control(phase="配音異常檢查"):
                        return

                if mode == "all" and pause_between_stages:
                    self.pause()
                    self.status_msg = "⏸️ [3/4 配音] 已合成完畢！已自動暫停供試聽台詞，確認無誤後請點擊「繼續合成」。"
                    if self.check_control(phase="配音審查"):
                        return

            # ========================
            # 階段 4: 合成 1080p 成片
            # ========================
            if mode in ("all", "compose"):
                self.stage = "🎬 [4/4 成片]"
                self.status_msg = "正在檢查分鏡素材完整度..."

                scenes_dir = self.job_path / "scenes"
                scene_folders = sorted([p for p in scenes_dir.iterdir() if p.is_dir()]) if scenes_dir.is_dir() else []
                missing_images = [s.name for s in scene_folders if not (s / "image.png").is_file()]
                missing_audios = [s.name for s in scene_folders if not (s / "speech.wav").is_file()]

                if missing_images or missing_audios:
                    err_details = []
                    if missing_images:
                        err_details.append(f"缺圖: {', '.join(missing_images[:4])}{'...' if len(missing_images) > 4 else ''}")
                    if missing_audios:
                        err_details.append(f"缺音: {', '.join(missing_audios[:4])}{'...' if len(missing_audios) > 4 else ''}")
                    self.pause()
                    self.status_msg = f"⚠️ [4/4 成片暫停] 分鏡素材未就緒 ({' ｜ '.join(err_details)})。請點擊「繼續執行」補產出，或於看板單獨處理。"
                    if self.check_control(phase="成片素材確認"):
                        return

                self.status_msg = "正在透過 FFmpeg 合成 1080p 影片、推鏡、畫中畫與字幕..."
                self.progress = 0.92 if mode == "all" else 0.5
                if self.check_control(phase="成片準備"):
                    return

                cmd_args = CmdArgs(job=self.job_path, check_control=self.check_control)
                ret_comp = run_compose(cmd_args)
                if ret_comp != 0:
                    self.error_msg = "FFmpeg 成片合成失敗，請檢查分鏡素材是否齊全或 FFmpeg 日誌。"
                    self.status_msg = "❌ 成片合成失敗"
                    return

                generate_preview_html(self.job_path)

            if not self._stop_event.is_set():
                self.progress = 1.0
                self.is_done = True
                self.status_msg = "🎉 任務大功告成！全片分鏡、語音與 1080p 成片已準備就緒。"
            else:
                self.status_msg = "⏹️ 任務已中止。已完成的分鏡均已妥善保存。"

        except Exception as exc:
            self.error_msg = str(exc)
            self.status_msg = f"❌ 執行中斷: {exc}"
        finally:
            with self._lock:
                self.is_running = False
                if self._stop_event.is_set():
                    self.is_stopped = True


# 全域 Job 執行器快取（以 job_name 為索引，跨頁面刷新保持狀態）
_GLOBAL_RUNNERS: dict[str, PipelineRunner] = {}


def get_pipeline_runner(job_name: str, job_path: Path) -> PipelineRunner:
    """取得或建立指定專案的背景任務控制器。"""
    if job_name not in _GLOBAL_RUNNERS:
        _GLOBAL_RUNNERS[job_name] = PipelineRunner(job_name, job_path)
    else:
        # 更新路徑（若有變更）
        _GLOBAL_RUNNERS[job_name].job_path = job_path
    return _GLOBAL_RUNNERS[job_name]
