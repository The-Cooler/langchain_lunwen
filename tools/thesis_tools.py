"""
论文相关的通用工具函数。

说明：
- 这里放的是可被多个 Agent / CLI / 测试复用的“纯工具”逻辑；
- Agent 层（如 ThesisReActAgent）只负责编排与状态管理，本文件不关心对话流程。
"""

from __future__ import annotations

import re
from pathlib import Path

from core.context import get_chapter_spec_path

THINKING_PATTERNS = [
    re.compile(r"<thought>.*?</thought>", re.DOTALL),
    re.compile(r"思考[：:]\s*.*", re.DOTALL),
    re.compile(r"我认为[^。]+。"),
    re.compile(r"接下来(我们)?(要)?[^。]+。"),
]


def strip_thinking_from_content(content: str) -> str:
    """从待写入内容中移除思考类片段，只保留正式正文。"""
    if not content or not content.strip():
        return ""
    text = content.strip()
    for pat in THINKING_PATTERNS:
        text = pat.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def validate_docx_path(docx_path: str | Path) -> str:
    """
    验证 docx：检查是否全部为黑色字体、是否含有思考内容。
    返回观察描述字符串。
    """
    from docx import Document
    from docx.shared import RGBColor

    path = Path(docx_path)
    if not path.exists():
        return f"文件不存在：{path}"
    try:
        doc = Document(str(path))
    except Exception as e:
        return f"无法打开文档：{e}"

    black = RGBColor(0, 0, 0)
    non_black = []
    thinking_like = []
    for i, p in enumerate(doc.paragraphs):
        text = (p.text or "").strip()
        if not text:
            continue
        for run in p.runs:
            if run.font.color.rgb is not None and run.font.color.rgb != black:
                non_black.append((i + 1, text[:50]))
                break
        if "思考" in text or "<thought>" in text or "我认为" in text:
            thinking_like.append((i + 1, text[:80]))

    if non_black:
        return f"发现非黑色字体：第 {non_black[0][0]} 段等，请确保全文黑色。"
    if thinking_like:
        return f"发现疑似思考内容（不应出现在正文）：第 {thinking_like[0][0]} 段等。"
    return "验证通过：所有字体均为黑色，未发现思考内容。"


def validate_docx_path_with_ok(docx_path: str | Path) -> tuple[str, bool]:
    """验证 docx 并返回（描述字符串, 是否通过）。"""
    result = validate_docx_path(docx_path)
    text = result.lower()
    ok = any(k in text for k in ("通过", "pass", "ok", "无异常"))
    return result, ok


def get_progress_path(docx_path: str | Path) -> Path:
    """与给定 docx 同目录、同主名的 .progress.txt 路径。"""
    p = Path(docx_path)
    return p.parent / f"{p.stem}.progress.txt"


def append_progress(progress_path: Path, kind: str, title: str) -> None:
    """将本次写入位置追加到进度文件。kind 为 section 或 table。"""
    line = title.replace("\n", " ").replace("\r", "").strip()
    if not line:
        return
    with open(progress_path, "a", encoding="utf-8") as f:
        f.write(f"{kind}\t{line}\n")


def get_written_set(progress_path: Path) -> tuple[set[str], set[str]]:
    """从进度文件读取已写章节标题、已写表题集合。返回 (sections, tables)。"""
    sections: set[str] = set()
    tables: set[str] = set()
    if not progress_path.exists():
        return sections, tables
    with open(progress_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or "\t" not in line:
                continue
            kind, title = line.split("\t", 1)
            title = title.strip()
            if kind == "section":
                sections.add(title)
            elif kind == "table":
                tables.add(title)
    return sections, tables


def read_chapter_spec_impl(section_title: str) -> str:
    """根据章节标题读取规范文件内容，供 Agent 工具封装调用。"""
    path = get_chapter_spec_path(section_title)
    if path is None or not path.exists():
        return "（未找到该章规范文件，可调用终端命令查看规范文件是否存在。）"
    return path.read_text(encoding="utf-8")

