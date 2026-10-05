"""把 style_prefix 接到 image_prompt 前面，已有同樣前綴就不再拼一次。"""

from __future__ import annotations


def compose_styled_prompt(style_prefix: str, prompt: str) -> str:
    prefix = (style_prefix or "").strip().strip("，, ")
    body = (prompt or "").strip()
    if not prefix:
        return body
    if not body:
        return prefix
    if body.startswith(prefix):
        return body
    head = body[: max(len(prefix) + 12, 96)]
    if prefix in head:
        return body
    # 若為英文提示詞，使用英文逗號連接，避免中文標點觸發模型渲染中文字
    sep = ", " if not any("\u4e00" <= c <= "\u9fff" for c in prefix + body) else "，"
    return f"{prefix}{sep}{body}".strip("，, ")
