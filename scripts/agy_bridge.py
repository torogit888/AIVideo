"""Antigravity CLI (agy) Host Bridge Server.

Runs on the Windows host and listens on port 8099.
Allows AIVideo (running inside Docker Dev Container) to call `agy.exe` on the host,
leveraging the user's Antigravity Pro subscription for AI image and text generation
without requiring Google Cloud / Gemini API billing or API keys.
"""

from __future__ import annotations

import sys
# 強制即時輸出，避免 Windows 終端機緩衝延遲
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

import json
import os
from pathlib import Path
import re
import shutil
import socketserver
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8099
REPO_ROOT = Path(__file__).resolve().parents[1]

# 序列化 agy.exe 執行，並記錄當前正在出圖的鏡頭名稱
_GENERATION_LOCK = threading.Lock()
_CURRENT_SCENE: str | None = None


def get_scene_label(dest_path: Path, scene_id: str | None = None) -> str:
    s_id = (scene_id or "").strip()
    if not s_id or s_id.lower() == "takes":
        parts = list(dest_path.parts)
        if "scenes" in parts:
            idx = parts.index("scenes")
            if idx + 1 < len(parts):
                s_id = parts[idx + 1]
        elif dest_path.parent.name.lower() != "takes":
            s_id = dest_path.parent.name
        else:
            s_id = dest_path.parent.parent.name

    if "第" in s_id and "幕" in s_id:
        return s_id
    m = re.match(r"^0*(\d+)", s_id)
    if m:
        num = int(m.group(1))
        return f"第 {num} 幕 ({s_id})"
    return s_id


def save_or_convert_image(src: Path, dest: Path) -> bool:
    """將來源圖片複製或轉換格式至目標路徑。"""
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        # 若來源與目標完全為同一個檔案，直接視為成功，避免 shutil.SameFileError
        try:
            if src.resolve() == dest.resolve():
                return True
        except Exception:
            if str(src.absolute()) == str(dest.absolute()):
                return True

        if src.suffix.lower() == dest.suffix.lower():
            shutil.copy2(str(src), str(dest))
            return True
        # 若副檔名不同（例如 subagent 產出 .jpg 而系統要求 .png），嘗試使用 pygame 轉檔
        try:
            import pygame
            surf = pygame.image.load(str(src))
            pygame.image.save(surf, str(dest))
            return True
        except Exception:
            shutil.copy2(str(src), str(dest))
            return True
    except Exception as e:
        print(f"[!] 複製或轉換圖片失敗: {e}")
        return False


def deliver_to_destinations(source_file: Path, primary_dest: Path, secondary_dest: Path | None = None) -> bool:
    """將生成的圖片直接存至主要目標（如分鏡底下的 image.png），並視需要同步一份至 secondary_dest。"""
    ok = save_or_convert_image(source_file, primary_dest)
    if secondary_dest:
        try:
            if secondary_dest.resolve() != primary_dest.resolve():
                save_or_convert_image(source_file, secondary_dest)
        except Exception:
            if str(secondary_dest.absolute()) != str(primary_dest.absolute()):
                save_or_convert_image(source_file, secondary_dest)
    return ok


class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def find_agy_path() -> Path | None:
    # 1. 優先檢查標準 Antigravity CLI 預設安裝路徑
    candidates = [
        Path.home() / ".gemini" / "bin" / "agy.exe",
        Path.home() / ".gemini" / "bin" / "agy",
        Path(os.environ.get("USERPROFILE", "")) / ".gemini" / "bin" / "agy.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Antigravity" / "bin" / "agy.exe",
    ]
    for c in candidates:
        if c.is_file():
            return c
    which = shutil.which("agy")
    if which:
        return Path(which)
    return None


def to_host_path(container_or_host_path: str) -> Path:
    p_str = container_or_host_path.strip()
    if p_str.startswith("/workspace/"):
        rel = p_str[len("/workspace/") :].lstrip("/\\")
        return REPO_ROOT / rel
    if p_str.startswith("/workspace"):
        return REPO_ROOT
    p = Path(p_str)
    if not p.is_absolute():
        return REPO_ROOT / p
    return p


class AgyBridgeHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        if self.path in ("/health", "/status", "/api/status"):
            agy = find_agy_path()
            self._send_json(
                200,
                {
                    "status": "available" if agy else "not_found",
                    "agy_path": str(agy) if agy else None,
                    "repo_root": str(REPO_ROOT),
                    "pro_authenticated": bool(agy),
                    "message": "Antigravity CLI (Pro) 橋接服務正常運作中" if agy else "找不到 agy.exe",
                },
            )
            return
        self._send_json(404, {"error": "Not Found"})

    def do_POST(self):
        if self.path == "/generate-image":
            agy = find_agy_path()
            if not agy:
                self._send_json(500, {"error": "找不到 Antigravity CLI (agy.exe) 執行檔"})
                return

            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length).decode("utf-8")
            try:
                payload = json.loads(raw_body)
            except Exception as e:
                self._send_json(400, {"error": f"JSON 解析失敗: {e}"})
                return

            prompt = payload.get("prompt", "").strip()
            dest_raw = payload.get("dest_path", "").strip()
            aspect_ratio = payload.get("aspect_ratio", "16:9").strip()

            if not prompt or not dest_raw:
                self._send_json(400, {"error": "缺少 prompt 或 dest_path 參數"})
                return

            dest_path = to_host_path(dest_raw)
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # 依使用者需求：若位於分鏡目錄內，主要儲存目標一律為該分鏡根目錄底下的 image.png
            scene_dir = None
            parts = list(dest_path.parts)
            if "scenes" in parts:
                idx = parts.index("scenes")
                if idx + 1 < len(parts):
                    scene_dir = Path(*parts[: idx + 2])

            if scene_dir:
                primary_dest = scene_dir / "image.png"
            else:
                primary_dest = dest_path

            task_prompt = (
                f"Use the image-generator subagent to generate an image.\n"
                f"Visual Prompt:\n{prompt}\n\n"
                f"Aspect ratio: {aspect_ratio}\n"
                f"Save the generated image file directly to: {primary_dest}\n"
                f"Return only the absolute file path of the saved image."
            )

            cmd = [
                str(agy),
                "-p",
                task_prompt,
                "--dangerously-skip-permissions",
                "--output-format",
                "text",
            ]

            global _CURRENT_SCENE
            scene_label = get_scene_label(dest_path, payload.get("scene_id"))

            if not _GENERATION_LOCK.acquire(blocking=False):
                busy_msg = f"（目前「{_CURRENT_SCENE}」正在出圖中）" if _CURRENT_SCENE else ""
                print(f"[!] 收到生圖請求: {scene_label}，但資源已被佔用 {busy_msg}，立即回傳已佔用")
                self._send_json(
                    429,
                    {
                        "success": False,
                        "busy": True,
                        "error": f"Antigravity CLI 目前正忙碌中{busy_msg}，資源已佔用，請稍後再試",
                    },
                )
                return

            _CURRENT_SCENE = scene_label
            t_start = time.time()
            try:
                print(f"[*] 開始透過 agy.exe 執行生圖: {scene_label} -> {primary_dest.name}", flush=True)
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                # 即時心跳與耗時顯示，讓終端機不再卡住無反應
                while proc.poll() is None:
                    time.sleep(3.0)
                    elapsed = round(time.time() - t_start, 1)
                    if proc.poll() is None:
                        print(f"    [~] {scene_label} AI 繪圖中... (已耗時 {elapsed}s)", flush=True)

                stdout, stderr = proc.communicate()
                stdout = stdout.strip() if stdout else ""
                stderr = stderr.strip() if stderr else ""
                elapsed = round(time.time() - t_start, 1)
                print(f"[+] agy.exe 執行完成 (耗時 {elapsed}s)，回傳代碼: {proc.returncode}", flush=True)

                # 1. 檢查 primary_dest 是否已直接生成
                if primary_dest.is_file() and primary_dest.stat().st_size > 1000:
                    deliver_to_destinations(primary_dest, primary_dest, dest_path)
                    mb_size = round(primary_dest.stat().st_size / (1024 * 1024), 2)
                    print(f"[✓] {scene_label} 出圖成功！已直接存檔至: {primary_dest} (大小: {mb_size} MB)")
                    self._send_json(
                        200,
                        {
                            "success": True,
                            "dest_path": str(dest_path),
                            "primary_path": str(primary_dest),
                            "size": primary_dest.stat().st_size,
                            "message": f"{scene_label} 已成功生成並存檔至 {primary_dest.name}",
                        },
                    )
                    return

                # 2. 備援：解析 stdout 中出現的檔案路徑（支援 /、\ 與 file:/// 格式）
                found_paths = re.findall(
                    r"(?:file:///)?([A-Za-z]:[/\\][^'\"\r\n<>]+\.(?:png|jpg|jpeg|webp))",
                    stdout,
                    flags=re.IGNORECASE,
                )
                for cand in reversed(found_paths):
                    p_cand = Path(cand.replace("/", "\\").strip())
                    if p_cand.is_file() and p_cand.stat().st_size > 1000:
                        if deliver_to_destinations(p_cand, primary_dest, dest_path):
                            mb_size = round(primary_dest.stat().st_size / (1024 * 1024), 2)
                            print(f"[✓] {scene_label} 出圖成功 (自輸出路徑複製)！已存至: {primary_dest} (大小: {mb_size} MB)")
                            self._send_json(
                                200,
                                {
                                    "success": True,
                                    "dest_path": str(dest_path),
                                    "primary_path": str(primary_dest),
                                    "size": primary_dest.stat().st_size,
                                    "message": f"{scene_label} 已成功複製並存檔至 {primary_dest.name}",
                                },
                            )
                            return

                # 3. 備援：直接掃描 brain 目錄下在本次執行期間產生的最新圖片
                brain_dir = Path.home() / ".gemini" / "antigravity" / "brain"
                if brain_dir.is_dir():
                    recent_imgs = []
                    for img in brain_dir.rglob("*"):
                        if img.is_file() and img.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                            try:
                                st = img.stat()
                                if st.st_mtime >= t_start - 10 and st.st_size > 1000:
                                    recent_imgs.append((st.st_mtime, img))
                            except Exception:
                                pass
                    if recent_imgs:
                        recent_imgs.sort(key=lambda x: x[0], reverse=True)
                        newest_img = recent_imgs[0][1]
                        if deliver_to_destinations(newest_img, primary_dest, dest_path):
                            mb_size = round(primary_dest.stat().st_size / (1024 * 1024), 2)
                            print(f"[✓] {scene_label} 出圖成功 (自 brain 捕獲最新圖片)！已存至: {primary_dest} (大小: {mb_size} MB)")
                            self._send_json(
                                200,
                                {
                                    "success": True,
                                    "dest_path": str(dest_path),
                                    "primary_path": str(primary_dest),
                                    "size": primary_dest.stat().st_size,
                                    "message": f"{scene_label} 已成功自 Antigravity brain 捕獲並存至 {primary_dest.name}",
                                },
                            )
                            return

                print(f"[✗] {scene_label} 未產出圖片檔案。Stdout: {stdout[:200]}")
                self._send_json(
                    500,
                    {
                        "success": False,
                        "error": f"{scene_label} Antigravity CLI 未產出圖片檔案。Stdout: {stdout[:300]} Stderr: {stderr[:300]}",
                    },
                )
            except Exception as exc:
                print(f"[✗] {scene_label} 呼叫 agy 失敗: {str(exc)}")
                self._send_json(500, {"success": False, "error": f"{scene_label} 呼叫 agy 失敗: {str(exc)}"})
            finally:
                _CURRENT_SCENE = None
                _GENERATION_LOCK.release()
            return

        self._send_json(404, {"error": "Not Found"})


def main():
    print(f"[*] 啟動 Antigravity CLI Bridge 服務 (port {PORT})...")
    agy = find_agy_path()
    if agy:
        print(f"[+] 找到 Antigravity CLI: {agy}")
    else:
        print("[!] 警告: 未找到 agy.exe，請確認已安裝 Google Antigravity")
    print(f"[+] 專案根目錄: {REPO_ROOT}")
    server = ThreadedHTTPServer(("0.0.0.0", PORT), AgyBridgeHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] 正在關閉 Bridge 服務...")
        server.server_close()


if __name__ == "__main__":
    main()
