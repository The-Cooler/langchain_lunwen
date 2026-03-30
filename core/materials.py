"""
素材相关工具：格式化、截断等，供 Agent 或其它模块使用。
"""

import re


def format_materials_preview(materials_text: str, max_chars: int = 50000) -> str:
    """返回素材内容预览（截断到 max_chars），供组织论文时参考。"""
    if not materials_text:
        return ""
    suffix = "…（已截断）" if len(materials_text) > max_chars else ""
    return materials_text[:max_chars] + suffix


def dedup_and_compress_materials(materials_text: str) -> str:
    """
    对素材做轻量压缩去重（按段落去重，保留首次出现顺序）。
    用于减少重复内容对后续轮次的干扰。
    """
    if not materials_text or not materials_text.strip():
        return ""
    blocks = re.split(r"\n\s*\n", materials_text.strip())
    seen: set[str] = set()
    kept: list[str] = []
    for block in blocks:
        b = block.strip()
        if not b:
            continue
        norm = re.sub(r"\s+", " ", b)
        if norm in seen:
            continue
        seen.add(norm)
        kept.append(b)
    return "\n\n".join(kept)
