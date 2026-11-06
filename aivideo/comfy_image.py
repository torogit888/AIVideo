from __future__ import annotations

import json
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

# 預設支援與建議的 Z-Image Turbo 核心檔案名稱
DEFAULT_UNET_NAME = "z_image_turbo_bf16.safetensors"
DEFAULT_CLIP_NAME = "qwen_3_4b.safetensors"
DEFAULT_VAE_NAME = "ae.safetensors"
DEFAULT_ILLUSTRIOUS_CKPT = "Illustrious-XL-v0.1.float8_e4m3fn.safetensors"
DEFAULT_CHIBI_LORA = "tekjin01929_Chibi_Style_Illust.safetensors"

# 常用比例與建議解析度（需符合 DiT / VAE 補丁大小，寬高建議皆為 16 或 64 的倍數）
ASPECT_RATIO_DIMENSIONS: dict[str, tuple[int, int]] = {
    "16:9": (1280, 720),
    "9:16": (720, 1280),
    "1:1": (1024, 1024),
    "4:3": (1152, 864),
    "3:4": (864, 1152),
    "21:9": (1536, 640),
}


def get_comfy_url() -> str:
    """自動偵測並取得當前環境最佳可用的 ComfyUI 服務端點 URL。"""
    env_url = os.environ.get("COMFY_URL", "").strip()
    if env_url:
        return env_url.rstrip("/")

    in_docker = Path("/.dockerenv").exists() or os.environ.get("DOCKER_CONTAINER") == "1"

    candidates = (
        ["http://comfyui:8188", "http://host.docker.internal:8188", "http://127.0.0.1:8188"]
        if in_docker
        else ["http://127.0.0.1:8188", "http://localhost:8188", "http://comfyui:8188"]
    )

    for cand in candidates:
        try:
            with urllib.request.urlopen(f"{cand}/system_stats", timeout=1) as resp:
                if 200 <= resp.status < 300:
                    return cand
        except Exception:
            continue

    # 若尚未啟動，回傳環境標準預設值
    return "http://comfyui:8188" if in_docker else "http://127.0.0.1:8188"


def is_comfyui_online(url: str | None = None) -> bool:
    """快速探測 ComfyUI 是否在線就緒。"""
    target = (url or get_comfy_url()).rstrip("/")
    try:
        with urllib.request.urlopen(f"{target}/system_stats", timeout=2) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


def resolve_resolution(aspect_ratio: str = "16:9") -> tuple[int, int]:
    """將比例字串解析為合適的生成寬度與高度。"""
    ar = (aspect_ratio or "16:9").strip()
    if ar in ASPECT_RATIO_DIMENSIONS:
        return ASPECT_RATIO_DIMENSIONS[ar]

    # 解析自定義寬高 (例如 1280x720)
    if "x" in ar.lower():
        parts = ar.lower().split("x")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            w = (int(parts[0]) // 16) * 16
            h = (int(parts[1]) // 16) * 16
            return max(w, 256), max(h, 256)

    return ASPECT_RATIO_DIMENSIONS["16:9"]


def resolve_ref_image_path(ref_path: str | Path) -> Path | None:
    """智慧解析參考圖路徑（支援專案相對路徑、容器 /workspace 路徑、Windows 絕對路徑）。"""
    if not ref_path:
        return None
    p = Path(ref_path)
    if p.is_file():
        return p
    p_str = str(ref_path).replace("\\", "/")
    if p_str.startswith("/workspace/"):
        cand = REPO_ROOT / p_str[len("/workspace/"):]
        if cand.is_file():
            return cand
    if ":" in p_str:
        parts = p_str.split("AIVideo/", 1)
        if len(parts) == 2:
            cand = REPO_ROOT / parts[1]
            if cand.is_file():
                return cand
    cand = REPO_ROOT / p
    if cand.is_file():
        return cand
    return None


def upload_image_to_comfyui(comfy_url: str, image_source: Path | bytes | str) -> str:
    """上傳參考圖至 ComfyUI 的 input 目錄，返回 ComfyUI 內建物件名稱。"""
    import requests

    if isinstance(image_source, (str, Path)):
        resolved = resolve_ref_image_path(image_source)
        if not resolved or not resolved.is_file():
            raise FileNotFoundError(f"找不到參考圖檔案：{image_source}")
        filename = f"ref_{resolved.name}"
        data = resolved.read_bytes()
    else:
        filename = f"ref_{int(time.time() * 1000)}.png"
        data = image_source

    resp = requests.post(
        f"{comfy_url}/upload/image",
        files={"image": (filename, data)},
        data={"overwrite": "true"},
        timeout=20,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"上傳參考圖至 ComfyUI 失敗 ({resp.status_code})：{resp.text}")

    resp_json = resp.json()
    return str(resp_json.get("name") or filename)


def get_node_input_choices(comfy_url: str, node_name: str, input_key: str) -> list[str]:
    """向 ComfyUI 查詢指定節點的合法輸入值清單 (例如已安裝的模型列表)。"""
    try:
        with urllib.request.urlopen(f"{comfy_url}/object_info/{node_name}", timeout=3) as resp:
            info = json.loads(resp.read().decode("utf-8"))
            req = info.get(node_name, {}).get("input", {}).get("required", {})
            choices = req.get(input_key, [[]])[0]
            return choices if isinstance(choices, list) else []
    except Exception:
        return []


def discover_comfy_models(comfy_url: str) -> dict[str, str]:
    """動態向 ComfyUI 查詢本機已安裝的模型檔案，若檔名微調能自動配對。"""
    result = {
        "unet_name": DEFAULT_UNET_NAME,
        "clip_name": DEFAULT_CLIP_NAME,
        "vae_name": DEFAULT_VAE_NAME,
        "illustrious_ckpt": DEFAULT_ILLUSTRIOUS_CKPT,
        "chibi_lora": DEFAULT_CHIBI_LORA,
    }

    # 1. 偵測 UNET (Diffusion Models)
    unets = get_node_input_choices(comfy_url, "UNETLoader", "unet_name")
    for u in unets:
        u_lower = str(u).lower()
        if "z_image" in u_lower or "z-image" in u_lower or "zimage" in u_lower:
            result["unet_name"] = str(u)
            break

    # 2. 偵測 CLIP (Text Encoders)
    clips = get_node_input_choices(comfy_url, "CLIPLoader", "clip_name")
    for c in clips:
        c_lower = str(c).lower()
        if "qwen_3_4b" in c_lower or "qwen2.5_3b" in c_lower or "qwen" in c_lower:
            result["clip_name"] = str(c)
            break

    # 3. 偵測 VAE
    vaes = get_node_input_choices(comfy_url, "VAELoader", "vae_name")
    for v in vaes:
        v_lower = str(v).lower()
        if "ae.safetensors" in v_lower or v_lower == "ae" or "sd3" in v_lower:
            result["vae_name"] = str(v)
            break

    # 4. 偵測 Checkpoint (Illustrious / SDXL)
    ckpts = get_node_input_choices(comfy_url, "CheckpointLoaderSimple", "ckpt_name")
    for ck in ckpts:
        ck_lower = str(ck).lower()
        if "illustrious" in ck_lower or "sdxl" in ck_lower:
            result["illustrious_ckpt"] = str(ck)
            break
    if ckpts and result["illustrious_ckpt"] == DEFAULT_ILLUSTRIOUS_CKPT and result["illustrious_ckpt"] not in ckpts:
        result["illustrious_ckpt"] = ckpts[0]

    # 5. 偵測 LoRA
    loras = get_node_input_choices(comfy_url, "LoraLoader", "lora_name")
    for lo in loras:
        lo_lower = str(lo).lower()
        if "tekjin01929" in lo_lower or "chibi" in lo_lower:
            result["chibi_lora"] = str(lo)
            break

    return result


def build_illustrious_prompt(
    prompt: str,
    negative_prompt: str = "",
    width: int = 1280,
    height: int = 720,
    seed: int = 0,
    steps: int = 24,
    cfg: float = 6.0,
    sampler_name: str = "euler_ancestral",
    scheduler: str = "karras",
    checkpoint_name: str = DEFAULT_ILLUSTRIOUS_CKPT,
    lora_name: str | None = None,
    lora_strength: float = 0.85,
    ref_image_name: str | None = None,
    denoise: float = 0.75,
) -> dict[str, Any]:
    """建構符合 ComfyUI 規範的 Illustrious-XL / SDXL 生圖工作流節點圖，完整支援二次元 LoRA 與圖生圖。"""
    clean_lora = (lora_name or "").strip()
    has_lora = bool(clean_lora and clean_lora.lower() not in ("none", "null", "無", "false", "0"))

    # 若使用 chibi lora 且正面詞未含觸發詞，自動注入 chibi_style
    final_prompt = prompt.strip()
    if has_lora and ("chibi" in clean_lora.lower() or "tekjin" in clean_lora.lower()):
        if "chibi_style" not in final_prompt.lower():
            final_prompt = f"chibi_style, {final_prompt}"

    default_neg = "worst quality, low quality, bad anatomy, bad hands, bad feet, missing fingers, extra digits, blurry, cropped, watermark, text, signature"
    final_negative = negative_prompt.strip() if negative_prompt and negative_prompt.strip() else default_neg

    graph: dict[str, Any] = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": checkpoint_name,
            },
        },
    }

    if has_lora:
        graph["lora"] = {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": clean_lora,
                "strength_model": lora_strength,
                "strength_clip": lora_strength,
                "model": ["1", 0],
                "clip": ["1", 1],
            },
        }
        model_source = ["lora", 0]
        clip_source = ["lora", 1]
    else:
        model_source = ["1", 0]
        clip_source = ["1", 1]

    graph["2"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": final_prompt,
            "clip": clip_source,
        },
    }
    graph["3"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": final_negative,
            "clip": clip_source,
        },
    }

    if ref_image_name:
        graph["4_load"] = {
            "class_type": "LoadImage",
            "inputs": {
                "image": ref_image_name,
            },
        }
        graph["4_scale"] = {
            "class_type": "ImageScale",
            "inputs": {
                "image": ["4_load", 0],
                "upscale_method": "bicubic",
                "width": width,
                "height": height,
                "crop": "center",
            },
        }
        graph["4_latent"] = {
            "class_type": "VAEEncode",
            "inputs": {
                "pixels": ["4_scale", 0],
                "vae": ["1", 2],
            },
        }
        latent_source = ["4_latent", 0]
        actual_denoise = denoise if (0.0 < denoise <= 1.0) else 0.75
    else:
        graph["4"] = {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1,
            },
        }
        latent_source = ["4", 0]
        actual_denoise = 1.0

    graph["5"] = {
        "class_type": "KSampler",
        "inputs": {
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler_name,
            "scheduler": scheduler,
            "denoise": actual_denoise,
            "model": model_source,
            "positive": ["2", 0],
            "negative": ["3", 0],
            "latent_image": latent_source,
        },
    }
    graph["6"] = {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": ["5", 0],
            "vae": ["1", 2],
        },
    }
    graph["7"] = {
        "class_type": "SaveImage",
        "inputs": {
            "images": ["6", 0],
            "filename_prefix": "illustrious_xl",
        },
    }
    return graph


def build_z_image_turbo_prompt(
    prompt: str,
    negative_prompt: str = "",
    width: int = 1280,
    height: int = 720,
    seed: int = 0,
    steps: int = 8,
    cfg: float = 1.0,
    unet_name: str = DEFAULT_UNET_NAME,
    clip_name: str = DEFAULT_CLIP_NAME,
    vae_name: str = DEFAULT_VAE_NAME,
    ref_image_name: str | None = None,
    denoise: float = 1.0,
    lora_name: str | None = None,
    lora_strength: float = 1.0,
) -> dict[str, Any]:
    """建構符合 ComfyUI API 規範的 Z-Image Turbo 工作流節點圖。若有提供參考圖則啟用圖生圖模式；若有提供 LoRA 則串接 LoraLoader。"""
    clean_lora = (lora_name or "").strip()
    has_lora = bool(clean_lora and clean_lora.lower() not in ("none", "null", "無", "false", "0"))

    graph: dict[str, Any] = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": unet_name,
                "weight_dtype": "default",
            },
        },
        "3": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": clip_name,
                "type": "lumina2",
                "device": "default",
            },
        },
        "4": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": vae_name,
            },
        },
    }

    # 若指定了 LoRA 模型，在 UNETLoader 與 CLIPLoader 之後串接 LoraLoader 節點
    if has_lora:
        graph["lora"] = {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": clean_lora,
                "strength_model": lora_strength,
                "strength_clip": lora_strength,
                "model": ["1", 0],
                "clip": ["3", 0],
            },
        }
        model_source = ["lora", 0]
        clip_source = ["lora", 1]
    else:
        model_source = ["1", 0]
        clip_source = ["3", 0]

    graph["2"] = {
        "class_type": "ModelSamplingAuraFlow",
        "inputs": {
            "shift": 3.0,
            "model": model_source,
        },
    }

    graph["5"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": prompt,
            "clip": clip_source,
        },
    }

    # 負面提示詞處理：
    # Z-Image Turbo (Lumina-2 Turbo) 屬於 Flow Matching 蒸餾極速模型，官方規範必須維持 CFG = 1.0，
    # 負面分支固定連接 ConditioningZeroOut 節點。
    # 負面提示詞約束透過 Qwen 3.4B 大語言編碼器的提示詞語義（avoid/exclude）生效，
    # 避免在 6GB 顯存上因多重 CLIPTextEncode 節點導致顯存死鎖與超時。
    graph["6"] = {
        "class_type": "ConditioningZeroOut",
        "inputs": {
            "conditioning": ["5", 0],
        },
    }

    if ref_image_name:
        graph["7_load"] = {
            "class_type": "LoadImage",
            "inputs": {
                "image": ref_image_name,
            },
        }
        graph["7_scale"] = {
            "class_type": "ImageScale",
            "inputs": {
                "image": ["7_load", 0],
                "upscale_method": "bicubic",
                "width": width,
                "height": height,
                "crop": "center",
            },
        }
        graph["7_latent"] = {
            "class_type": "VAEEncode",
            "inputs": {
                "pixels": ["7_scale", 0],
                "vae": ["4", 0],
            },
        }
        latent_source = ["7_latent", 0]
        actual_denoise = denoise if (0.0 < denoise <= 1.0) else 0.75
    else:
        graph["7"] = {
            "class_type": "EmptySD3LatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1,
            },
        }
        latent_source = ["7", 0]
        actual_denoise = 1.0

    graph["8"] = {
        "class_type": "KSampler",
        "inputs": {
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": "res_multistep",
            "scheduler": "simple",
            "denoise": actual_denoise,
            "model": ["2", 0],
            "positive": ["5", 0],
            "negative": ["6", 0],
            "latent_image": latent_source,
        },
    }
    graph["9"] = {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": ["8", 0],
            "vae": ["4", 0],
        },
    }
    graph["10"] = {
        "class_type": "SaveImage",
        "inputs": {
            "images": ["9", 0],
            "filename_prefix": "z_image_turbo",
        },
    }
    return graph


def generate_image_via_comfyui(
    prompt: str,
    dest: Path,
    negative_prompt: str = "",
    aspect_ratio: str = "16:9",
    model: str | None = None,
    engine: str = "auto",
    seed: int | None = None,
    steps: int = 8,
    cfg: float = 1.0,
    denoise: float = 0.75,
    ref_image: Path | bytes | str | None = None,
    ref_images: list[Path | bytes | tuple[Path | bytes, str]] | None = None,
    lora_name: str | None = None,
    lora_strength: float = 1.0,
    timeout: int = 420,
) -> tuple[Path, str, int | None]:
    """透過本機或容器內的 ComfyUI 服務呼叫 Z-Image Turbo 或 Illustrious-XL 執行生圖或圖生圖。"""
    comfy_url = get_comfy_url()

    # 1. 檢查 ComfyUI 連線
    if not is_comfyui_online(comfy_url):
        raise RuntimeError(
            f"無法連線至 ComfyUI 服務端點 ({comfy_url})。\n"
            "請確認已啟動 ComfyUI 容器或本機服務：\n"
            "  docker compose --profile comfyui up -d comfyui\n"
            "或確認 COMFY_URL 環境變數設定正確。"
        )

    # 2. 解析解析度與 seed
    width, height = resolve_resolution(aspect_ratio)
    actual_seed = seed if (seed is not None and seed >= 0) else random.randint(1, 2**32 - 1)

    # 3. 處理參考圖上傳與提示詞補強
    final_prompt = prompt
    target_ref = ref_image
    if not target_ref and ref_images:
        first_ref = ref_images[0]
        target_ref = first_ref[0] if (isinstance(first_ref, tuple) and len(first_ref) == 2) else first_ref

    ref_image_name: str | None = None
    if target_ref:
        try:
            ref_image_name = upload_image_to_comfyui(comfy_url, target_ref)
        except Exception as up_err:
            print(f"[warn] 上傳參考圖至 ComfyUI 失敗 ({up_err})，回退為純文字生圖模式", file=sys.stderr)

    if ref_images:
        ref_notes: list[str] = []
        for item in ref_images:
            lbl = item[1] if (isinstance(item, tuple) and len(item) == 2) else ""
            if lbl:
                ref_notes.append(lbl)
        if ref_notes:
            final_prompt = f"Character visual design: {', '.join(ref_notes)}. {prompt}"

    # 4. 動態探索已安裝的模型名稱
    discovered = discover_comfy_models(comfy_url)

    # 5. 判斷生圖引擎 (Z-Image Turbo vs Illustrious-XL)
    model_str = (model or "").lower()
    engine_str = (engine or "auto").lower()
    is_illustrious = (
        engine_str in ("illustrious", "sdxl")
        or "illustrious" in model_str
        or "sdxl" in model_str
    )

    # 檢查 Illustrious 所需之模型與 LoRA 是否已安裝
    if is_illustrious:
        # 檢查底模
        ckpts = get_node_input_choices(comfy_url, "CheckpointLoaderSimple", "ckpt_name")
        if not ckpts or (discovered["illustrious_ckpt"] not in ckpts and not any("illustrious" in c.lower() or "sdxl" in c.lower() for c in ckpts)):
            raise RuntimeError(
                f"ComfyUI 尚未安裝 Illustrious-XL / SDXL 底模！\n"
                f"目前 models/checkpoints/ 內容：{ckpts or '無'}\n"
                "請先執行模型下載任務：\n"
                "  在 VS Code 執行 Task: AIVideo: 下載 Illustrious-XL 底模與 Chibi LoRA (~3.9GB)\n"
                "  或在終端機執行：python -u scripts/download_illustrious_models.py"
            )

        # 檢查 LoRA
        clean_lora_req = (lora_name or "").strip()
        if clean_lora_req and clean_lora_req.lower() not in ("none", "null", "無", "false", "0"):
            loras = get_node_input_choices(comfy_url, "LoraLoader", "lora_name")
            if clean_lora_req not in loras:
                raise RuntimeError(
                    f"ComfyUI 的 models/loras/ 目錄中找不到 LoRA 模型檔案：'{clean_lora_req}'\n"
                    f"目前已安裝的 LoRA：{loras or '無'}\n"
                    "請先取得該 LoRA 檔案：\n"
                    "  1. 在瀏覽器打開 https://civitai.com/models/1576277/tekjin01929s-chibi-style 點擊 Download\n"
                    "  2. 下載後放至 Downloads 資料夾，再執行 python -u scripts/download_illustrious_models.py 自動同步進容器\n"
                    "  （若想先跳過 LoRA 僅用底模生圖，可將 LoRA 欄位留空或填 None）"
                )

    # 6. 組裝 API 請求
    # 執行前可主動通知 ComfyUI 釋放快取與舊模型，確保在 6GB 顯存/記憶體設備上有充裕空間
    try:
        req_free = urllib.request.Request(
            f"{comfy_url}/free",
            data=b'{"unload_models": true, "free_memory": true}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_free, timeout=5):
            pass
    except Exception:
        pass

    if is_illustrious:
        # Illustrious-XL 專用參數調整
        illu_steps = steps if steps != 8 else 24
        illu_cfg = cfg if cfg != 1.0 else 6.0
        illu_lora = lora_name if lora_name else discovered.get("chibi_lora")
        prompt_graph = build_illustrious_prompt(
            prompt=final_prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            seed=actual_seed,
            steps=illu_steps,
            cfg=illu_cfg,
            checkpoint_name=discovered["illustrious_ckpt"],
            lora_name=illu_lora,
            lora_strength=lora_strength if lora_strength != 1.0 else 0.85,
            ref_image_name=ref_image_name,
            denoise=denoise,
        )
    else:
        # Z-Image Turbo 官方極速模式
        clean_neg = (negative_prompt or "").strip()
        if clean_neg:
            final_prompt = f"{final_prompt}, avoid: {clean_neg}, no {clean_neg}"

        prompt_graph = build_z_image_turbo_prompt(
            prompt=final_prompt,
            negative_prompt=clean_neg,
            width=width,
            height=height,
            seed=actual_seed,
            steps=steps,
            cfg=cfg,
            unet_name=discovered["unet_name"],
            clip_name=discovered["clip_name"],
            vae_name=discovered["vae_name"],
            ref_image_name=ref_image_name,
            denoise=denoise,
            lora_name=lora_name,
            lora_strength=lora_strength,
        )

    req_data = json.dumps({"prompt": prompt_graph}).encode("utf-8")
    req = urllib.request.Request(
        f"{comfy_url}/prompt",
        data=req_data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_msg = ""
        try:
            err_json = json.loads(e.read().decode("utf-8"))
            node_errors = err_json.get("node_errors", {})
            if node_errors:
                err_msg = f"節點錯誤：{json.dumps(node_errors, ensure_ascii=False)}"
            else:
                err_msg = err_json.get("error", {}).get("message") or str(err_json)
        except Exception:
            err_msg = str(e)
        raise RuntimeError(
            f"ComfyUI 接受生成請求失敗 (HTTP {e.code})：{err_msg}\n"
            "請檢查 ComfyUI 是否已放置對應模型：\n"
            f"  - Diffusion Model: models/diffusion_models/{discovered['unet_name']}\n"
            f"  - Text Encoder:    models/text_encoders/{discovered['clip_name']}\n"
            f"  - VAE:             models/vae/{discovered['vae_name']}"
        ) from e

    prompt_id = resp_data.get("prompt_id")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI 未返回 prompt_id，伺服器回應：{resp_data}")

    # 6. 輪詢生成結果
    image_info: dict[str, Any] | None = None
    start_time = time.time()
    while time.time() - start_time < timeout:
        time.sleep(1.0)
        try:
            with urllib.request.urlopen(f"{comfy_url}/history/{prompt_id}", timeout=5) as resp:
                hist = json.loads(resp.read().decode("utf-8"))
        except Exception:
            continue

        if prompt_id in hist:
            task_hist = hist[prompt_id]
            outputs = task_hist.get("outputs", {})
            for _, node_data in outputs.items():
                if isinstance(node_data, dict) and "images" in node_data and node_data["images"]:
                    image_info = node_data["images"][0]
                    break

            if image_info:
                break

            status = task_hist.get("status", {})
            if status.get("status_str") == "error":
                messages = status.get("messages", [])
                raise RuntimeError(f"ComfyUI 執行生成時發生錯誤：{messages}")

    if not image_info:
        # 若逾時，主動發送 interrupt，避免殘留任務卡住後續請求
        try:
            req_int = urllib.request.Request(
                f"{comfy_url}/interrupt",
                data=json.dumps({"prompt_id": prompt_id}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req_int, timeout=5):
                pass
        except Exception:
            pass
        raise TimeoutError(f"等待 ComfyUI Z-Image Turbo 生圖逾時 ({timeout} 秒)")

    # 7. 下載並存檔
    query = urllib.parse.urlencode({
        "filename": image_info["filename"],
        "subfolder": image_info.get("subfolder", ""),
        "type": image_info.get("type", "output"),
    })
    view_url = f"{comfy_url}/view?{query}"
    with urllib.request.urlopen(view_url, timeout=30) as resp:
        image_bytes = resp.read()

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(image_bytes)

    # 生圖結束後主動釋放顯存快取，避免殘留佔用影響後續任務
    try:
        req_free = urllib.request.Request(
            f"{comfy_url}/free",
            data=b'{"unload_models": true, "free_memory": true}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_free, timeout=5):
            pass
    except Exception:
        pass

    return dest, "comfyui:z-image-turbo", actual_seed

