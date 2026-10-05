from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

MAX_CHARACTERS = 8
MAX_REF_IMAGES = 6

_CHAR_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,47}$")


def slug_character_id(name: str, used: set[str] | None = None, index: int = 1) -> str:
    used = used if used is not None else set()
    ascii_part = (
        unicodedata.normalize("NFKD", name or "")
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    ascii_part = re.sub(r"[^a-z0-9]+", "_", ascii_part).strip("_")[:40]
    base = ascii_part or f"char_{index}"
    cid = base
    n = 2
    while cid in used:
        cid = f"{base}_{n}"
        n += 1
    used.add(cid)
    return cid


def compose_subject_anchor(characters: list[dict[str, str]]) -> str:
    parts: list[str] = []
    for ch in characters:
        name = str(ch.get("name") or "").strip()
        appearance = str(ch.get("appearance") or "").strip()
        if name and appearance:
            parts.append(f"{name}: {appearance}")
        elif appearance:
            parts.append(appearance)
        elif name:
            parts.append(name)
    return " | ".join(parts)


def normalize_characters(raw: Iterable[Any] | None) -> list[dict[str, str]]:
    """把分析結果或 API payload 收成穩定的 {id, name, appearance} 列表。"""
    if not raw:
        return []
    used: set[str] = set()
    out: list[dict[str, str]] = []
    for i, item in enumerate(raw, start=1):
        if len(out) >= MAX_CHARACTERS:
            break
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip() or f"Character {i}"
        appearance = str(item.get("appearance") or item.get("subject_anchor") or "").strip()
        raw_id = str(item.get("id") or "").strip().lower()
        if _CHAR_ID_RE.match(raw_id) and raw_id not in used:
            used.add(raw_id)
            cid = raw_id
        else:
            cid = slug_character_id(name, used, index=i)
        out.append({"id": cid, "name": name, "appearance": appearance})
    return out


def characters_from_subject(subject: str) -> list[dict[str, str]]:
    subject = (subject or "").strip()
    if not subject:
        return []
    return [{"id": "main", "name": "Main Subject", "appearance": subject}]


def ensure_characters(v_anchors: dict[str, Any] | None) -> list[dict[str, str]]:
    v_anchors = v_anchors if isinstance(v_anchors, dict) else {}
    chars = normalize_characters(v_anchors.get("characters"))
    if chars:
        return chars
    return characters_from_subject(str(v_anchors.get("subject") or ""))


def character_image_path(job_dir: Path, char_id: str) -> Path:
    return job_dir / "characters" / f"{char_id}.png"


def legacy_hero_path(job_dir: Path) -> Path:
    return job_dir / "hero_anchor.png"


def character_has_image(job_dir: Path, char_id: str) -> bool:
    return character_image_path(job_dir, char_id).is_file()


def attach_legacy_hero_to_first(job_dir: Path, characters: list[dict[str, str]]) -> None:
    """舊專案只有 hero_anchor.png 時，複製給第一個角色當定裝圖。"""
    hero = legacy_hero_path(job_dir)
    if not hero.is_file() or not characters:
        return
    first = characters[0]
    dest = character_image_path(job_dir, first["id"])
    if dest.is_file():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(hero.read_bytes())


def character_image_url(job_id: str, char_id: str, job_dir: Path) -> str | None:
    path = character_image_path(job_dir, char_id)
    if not path.is_file():
        return None
    import urllib.parse
    job_id_encoded = urllib.parse.quote(job_id)
    mtime = int(path.stat().st_mtime)
    return f"/media/jobs/{job_id_encoded}/characters/{char_id}.png?t={mtime}"


def first_hero_url(job_id: str, job_dir: Path, characters: list[dict[str, str]]) -> tuple[bool, str | None]:
    for ch in characters:
        url = character_image_url(job_id, ch["id"], job_dir)
        if url:
            return True, url
    hero = legacy_hero_path(job_dir)
    if hero.is_file():
        import urllib.parse
        job_id_encoded = urllib.parse.quote(job_id)
        mtime = int(hero.stat().st_mtime)
        return True, f"/media/jobs/{job_id_encoded}/hero_anchor.png?t={mtime}"
    return False, None


def collect_character_ref_images(
    job_dir: Path,
    v_anchors: dict[str, Any] | None,
) -> list[tuple[Path, str]]:
    """出圖用的多模態參考圖：每人一張，最多 MAX_REF_IMAGES。"""
    v_anchors = v_anchors if isinstance(v_anchors, dict) else {}
    if not v_anchors.get("use_image_reference", True):
        return []

    characters = ensure_characters(v_anchors)
    attach_legacy_hero_to_first(job_dir, characters)

    refs: list[tuple[Path, str]] = []
    for ch in characters:
        if len(refs) >= MAX_REF_IMAGES:
            break
        path = character_image_path(job_dir, ch["id"])
        if not path.is_file():
            continue
        name = ch.get("name") or ch["id"]
        appearance = (ch.get("appearance") or "").strip()
        label = f'character "{name}"'
        if appearance:
            label += f" ({appearance[:220]})"
        refs.append((path, label))

    if refs:
        return refs

    hero = legacy_hero_path(job_dir)
    if hero.is_file():
        return [(hero, "the primary visual subject / character")]
    return []


def collect_scene_character_ref_images(
    job_dir: Path,
    v_anchors: dict[str, Any] | None,
    narration: str = "",
    image_prompt: str = "",
) -> list[tuple[Path, str]]:
    """針對特定場景分鏡，依據台詞與出圖 Prompt 智慧篩選出場角色的定裝圖，避免全體角色圖混雜干擾一致性。"""
    all_refs = collect_character_ref_images(job_dir, v_anchors)
    if not all_refs:
        return []

    characters = ensure_characters(v_anchors)
    if not characters or len(characters) <= 1:
        return all_refs

    combined_text = f"{narration} {image_prompt}".lower()

    # 比對各角色關鍵字
    matched_refs: list[tuple[Path, str]] = []
    for ch in characters:
        ch_id = str(ch.get("id") or "").lower()
        ch_name = str(ch.get("name") or "").lower()
        # 拆解中文名、英文名關鍵字
        tokens = set(re.findall(r"[\w\u4e00-\u9fff]+", f"{ch_id} {ch_name}"))
        # 過濾太短的無意義通用字
        tokens = {t for t in tokens if len(t) >= 2 and t not in {"角色", "char", "character", "main"}}

        if any(t in combined_text for t in tokens):
            path = character_image_path(job_dir, ch["id"])
            if path.is_file():
                name = ch.get("name") or ch["id"]
                appearance = (ch.get("appearance") or "").strip()
                label = f'character "{name}"'
                if appearance:
                    label += f" ({appearance[:220]})"
                matched_refs.append((path, label))

    # 若精準匹配到 1~2 位出場角色，只傳這幾位！
    if matched_refs:
        return matched_refs[:MAX_REF_IMAGES]

    # 若未特別指名某角色，僅回傳第一位主角的定裝圖，不傳入其餘無關角色，保證主體穩定
    first_path = character_image_path(job_dir, characters[0]["id"])
    if first_path.is_file():
        ch0 = characters[0]
        name0 = ch0.get("name") or ch0["id"]
        app0 = (ch0.get("appearance") or "").strip()
        label0 = f'character "{name0}"'
        if app0:
            label0 += f" ({app0[:220]})"
        return [(first_path, label0)]

    return all_refs[:1]


def persist_characters_on_anchors(
    v_anchors: dict[str, Any],
    characters: list[dict[str, str]],
) -> dict[str, Any]:
    v_anchors["characters"] = [
        {"id": ch["id"], "name": ch["name"], "appearance": ch.get("appearance", "")}
        for ch in characters
    ]
    composed = compose_subject_anchor(characters)
    if composed:
        v_anchors["subject"] = composed
    return v_anchors


def character_bible_for_prompts(characters: list[dict[str, str]]) -> str:
    if not characters:
        return ""
    lines = []
    for ch in characters:
        name = ch.get("name") or ch.get("id") or "Character"
        appearance = (ch.get("appearance") or "").strip() or "distinct, consistent appearance"
        lines.append(f'- "{name}": {appearance}')
    return "\n".join(lines)


def now_cache_bust() -> int:
    return int(datetime.now().timestamp())


def prune_character_images(job_dir: Path, keep_ids: Iterable[str]) -> None:
    keep = set(keep_ids)
    folder = job_dir / "characters"
    if not folder.is_dir():
        return
    for path in folder.glob("*.png"):
        if path.stem not in keep:
            path.unlink(missing_ok=True)


def build_character_hero_prompt(
    style_prefix: str,
    name: str,
    appearance: str,
    environment: str = "",
) -> str:
    """構建乾淨純粹的定裝基準圖 Prompt，智慧感知主體是人物還是核心物件/載具，避免非人物體被擬人化。"""
    prefix = (style_prefix or "").strip("，")
    char_desc = f"{name}: {appearance}" if name and appearance else (appearance or name)

    combined_text = f"{name} {appearance}".lower()

    # 判定是否為物品、道具、飲料、載具、機器等非人物實體
    object_keywords = (
        "bottle", "can", "drink", "beverage", "soda", "pepsi", "coke",
        "submarine", "ship", "cruiser", "destroyer", "boat", "vessel", "fleet", "warship",
        "plane", "aircraft", "car", "tank", "vehicle", "machine", "device", "apparatus",
        "prop", "artifact", "weapon", "sword", "gun", "glass", "container",
        "telescope", "satellite", "rocket", "station", "building", "chip", "wafer"
    )
    person_keywords = (
        "kendall", "nixon", "khrushchev", "person", "man", "woman", "boy", "girl",
        "president", "leader", "ceo", "captain", "sailor", "soldier", "character", "official"
    )

    is_object = any(k in combined_text for k in object_keywords) and not any(p in name.lower() for p in person_keywords)

    sep = ", " if not any("\u4e00" <= c <= "\u9fff" for c in prefix) else "，"

    if is_object:
        # 物件/道具/載具展示模板：強調物品本體細節與材質，嚴禁擬人化或長出手腳
        return (
            f"{prefix}{sep}Iconic object design reference sheet, SINGLE item only, central hero display of the physical object, "
            f"strictly an inanimate physical object, authentic structural scale and geometry, realistic materials and textures, "
            f"absolutely NO eyes, NO mouth, NO face, NO arms, NO legs, NO hands, NO feet, NO limbs, NO personification, NO anthropomorphism, "
            f"no human figures, no people, no anime characters, no extra clutter, no text, no labels, no watermarks, "
            f"{char_desc}, "
            f"clean minimalist neutral studio background, soft even studio lighting, 16:9 widescreen composition"
        ).strip("，, ")
    else:
        # 人物/角色立繪模板：專注於全身比例、面部五官與服飾
        return (
            f"{prefix}{sep}Character reference sheet, SINGLE character only, full-body standing pose, "
            f"clear face, distinct hair, body proportions and signature outfit colors, "
            f"no other characters, no collage, no extra props, no text, no labels, no watermarks, "
            f"{char_desc}, "
            f"clean minimalist neutral background, soft even lighting, 16:9 widescreen composition"
        ).strip("，, ")
