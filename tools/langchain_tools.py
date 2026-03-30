"""LangChain 工具工厂：创建论文生成所需的全部工具，通过闭包共享状态。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from functools import lru_cache
from langchain_core.tools import tool

from core.context import (
    get_chapter_spec_path,
    get_config_profile_name,
    get_skill_dir,
    load_template_content,
)
from tools.chapter_spec_tools import debug_chapter_spec
from tools.terminal_tools import run_terminal_command_with_confirm
from tools.thesis_tools import (
    get_progress_path,
    get_written_set,
    read_chapter_spec_impl,
    validate_docx_path_with_ok,
)
from tools.word_tools import (
    ensure_word_builder,
    write_figure_caption_into_docx,
    write_section_into_docx,
    write_table_into_docx,
)

_FORMAT_SPEC_MAP = {
    "论文助手": "论文助手.md",
    "索引": "论文要求-索引.md",
    "页面设置": "论文要求-页面设置.md",
    "字体与字号": "论文要求-字体与字号.md",
    "段落与排版": "论文要求-段落与排版.md",
    "其他要求": "论文要求-其他要求.md",
}

_PARENS_SPLIT_RE = re.compile(r"[（(]")
_WHITESPACE_RE = re.compile(r"\s+")
_NUM_HEADING_RE = re.compile(r"^\s*-\s*(\d+\.\d+(?:\.\d+)?)\s+(.+?)\s*$")


def _normalize_title_for_compare(s: str) -> str:
    s = (s or "").strip()
    s = _PARENS_SPLIT_RE.split(s, maxsplit=1)[0].strip()
    # 细则行常用“：xxx字/项”或“：xxx要求”，段落标题一般不包含这些后缀
    s = s.split("：", 1)[0].strip()
    s = s.split(":", 1)[0].strip()
    # 例如 spec: “2.2.3 系统用例模型是对系统中xxx的整体描述。”，
    # progress 通常只写到“2.2.3 系统用例模型”
    if "是对" in s:
        s = s.split("是对", 1)[0].strip()
    s = _WHITESPACE_RE.sub(" ", s)
    return s


def _truncate_parens(s: str) -> str:
    s = (s or "").strip()
    s = _PARENS_SPLIT_RE.split(s, maxsplit=1)[0].strip()
    s = s.split("：", 1)[0].strip()
    s = s.split(":", 1)[0].strip()
    if "是对" in s:
        s = s.split("是对", 1)[0].strip()
    return s


@lru_cache(maxsize=4)
def _get_expected_section_order_cached(profile_name: str) -> tuple[list[str], dict[str, str]]:
    """
    构建“应写入标题”的线性顺序（归一化后的标题序列 + 归一化->原始标题映射）。

    依据：template.md（顶层章顺序） + chapters/*.md（抽取带 1.1/1.2/1.2.1/3.2.2 这类编号的要求标题）
    """
    # 注意：调用方应已通过 set_config_profile(profile_name) 切换到该 profile
    template_text = load_template_content()
    expected_raw: list[str] = []
    norm_to_raw: dict[str, str] = {}

    def _push(raw_title: str) -> None:
        raw_title = (raw_title or "").strip()
        if not raw_title:
            return
        n = _normalize_title_for_compare(raw_title)
        if not n:
            return
        norm_to_raw.setdefault(n, raw_title)
        expected_raw.append(n)

    # 1) 顶层顺序：template 中的“第x章 ...”
    top_titles: list[str] = []
    for line in template_text.splitlines():
        s = line.strip()
        if not s:
            continue
        # - 第3章 系统总体设计
        if s.startswith("- 第") and "章" in s:
            top_titles.append(s[1:].strip())
        # 1. 摘要（中文）/2. ABSTRACT（英文摘要）这类也可能写入进度文件
        if s.startswith(("1.", "2.", "3.", "4.", "5.")) and ("摘要" in s or "ABSTRACT" in s or "致谢" in s):
            # 取点号后内容
            parts = s.split(".", 1)
            if len(parts) == 2:
                top_titles.append(parts[1].strip())

    # 2) 每个顶层章：抽取 chapters 中编号子标题（如 3.2.1、3.2.2、4.1.1）
    for top in top_titles:
        _push(top)
        m = re.match(r"^第(\d+)章", top)
        if not m:
            continue
        chap_no = m.group(1)
        spec_path = get_chapter_spec_path(top)
        if spec_path is None or not spec_path.exists():
            continue
        spec_text = spec_path.read_text(encoding="utf-8")
        # 只解析“结构”段落，避免从“字数/细则”中抽取到并非真实写入标题的条目
        m_struct = re.search(r"##\s*结构[^\n]*\n(.*?)(?=\n##\s*|\Z)", spec_text, flags=re.S)
        struct_text = m_struct.group(1) if m_struct else spec_text
        for line in struct_text.splitlines():
            # 只认形如：- 3.2.2 xxx 的要求行
            m2 = _NUM_HEADING_RE.match(line)
            if not m2:
                continue
            num = m2.group(1)  # 例如 3.2.2
            rest = m2.group(2)
            if not num.startswith(f"{chap_no}."):
                continue
            rest = _truncate_parens(rest)
            if not rest:
                continue
            # 标题格式：3.2.2 数据库表设计
            raw_title = f"{num} {rest}".strip()
            _push(raw_title)

    # 去重但保序
    seen: set[str] = set()
    ordered: list[str] = []
    for n in expected_raw:
        if n in seen:
            continue
        seen.add(n)
        ordered.append(n)
    return ordered, norm_to_raw


def get_expected_section_order() -> tuple[list[str], dict[str, str]]:
    """返回当前 profile 的期望标题顺序，用于断言不得跳写。"""
    prof = get_config_profile_name()
    return _get_expected_section_order_cached(prof)


class ThesisContext:
    """论文生成过程中的共享状态容器。"""

    def __init__(
        self,
        docx_path: Path,
        existing_docx_text: str | None,
        vectorstore,
    ):
        self.docx_path = docx_path
        self.existing_docx_text = existing_docx_text
        self.vectorstore = vectorstore
        self.word_builder = None
        self.validated_ok = False


def create_thesis_tools(ctx: ThesisContext) -> list:
    """根据共享状态创建 LangChain 工具列表（闭包模式）。"""
    expected_order_norm, expected_norm_to_raw = get_expected_section_order()
    expected_idx_map: dict[str, int] = {n: i for i, n in enumerate(expected_order_norm)}

    @tool
    def search_materials(query: str) -> str:
        """根据关键词或问题搜索素材库中的相关内容。撰写每一章节前应先搜索相关素材，确保内容有据可依。参数 query: 搜索关键词或问题描述。"""
        docs = ctx.vectorstore.similarity_search(query, k=8)
        if not docs:
            return "未找到相关素材。"
        parts = []
        for i, doc in enumerate(docs, 1):
            parts.append(f"【片段 {i}】\n{doc.page_content}")
        return "\n\n---\n\n".join(parts)

    @tool
    def read_format_spec(category: str) -> str:
        """按需读取论文格式规范。参数 category: 规范类别，可选值为「论文助手」「页面设置」「字体与字号」「段落与排版」「其他要求」「索引」。撰写前至少读取一次相关类别。"""
        filename = _FORMAT_SPEC_MAP.get(category)
        if not filename:
            return f"未知类别「{category}」。可选：{', '.join(_FORMAT_SPEC_MAP.keys())}"
        path = get_skill_dir() / filename
        if not path.exists():
            return f"规范文件不存在：{path}"
        return path.read_text(encoding="utf-8")

    @tool
    def read_chapter_spec(section_title: str) -> str:
        """读取某章的内容要求与结构细则。撰写或修改该章前先调用本工具。参数 section_title: 章节标题，如「摘要」「第1章 绪论」「致谢」。"""
        return read_chapter_spec_impl(section_title)

    @tool
    def debug_chapter_spec_tool(section_title: str) -> str:
        """调试用：当 read_chapter_spec 找不到规范文件时，调用本工具查看映射与已有规范文件情况。"""
        return debug_chapter_spec(section_title)

    @tool
    def run_terminal_command(command: str) -> str:
        """执行终端命令（执行前需人工确认），用于排查规范文件等问题。"""
        return run_terminal_command_with_confirm(command)

    @tool
    def write_section_to_docx(section_title: str, content: str) -> str:
        """将一节正式内容写入 Word 文档。section_title 为标题，content 为纯正文（可多段，用换行分隔）。严禁在 content 中写入思考过程或元内容，仅限论文正文。"""
        st = section_title.strip()
        if st == "参考文献" or st.startswith("参考文献 "):
            return "未写入：禁止自动生成「参考文献」章节及文献列表，请跳过。"

        progress_path = get_progress_path(ctx.docx_path)
        written_sections, _ = get_written_set(progress_path)
        st_norm = _normalize_title_for_compare(st)
        written_norm = {_normalize_title_for_compare(t) for t in written_sections if t}
        if st in written_sections or (st_norm and st_norm in written_norm):
            return f"该节已写入：「{st}」。请按模板写下一节，勿重复。"

        # 写入顺序断言：不得跳过 expected 标题序列中尚未写入的内容
        if st_norm in expected_idx_map:
            idx = expected_idx_map[st_norm]
            missing_before = [
                expected_norm_to_raw[expected_order_norm[i]]
                for i in range(0, idx)
                if expected_order_norm[i] not in written_norm
            ]
            if missing_before:
                return (
                    "未写全上一必需小节，拒绝跳写。\n"
                    f"缺失：{missing_before[0]}\n"
                    f"当前请求写入：{st}"
                )

        ctx.word_builder, ctx.docx_path = ensure_word_builder(
            ctx.word_builder, ctx.docx_path, ctx.existing_docx_text
        )
        result = write_section_into_docx(
            ctx.word_builder,
            ctx.docx_path,
            section_title,
            content,
            progress_path=progress_path,
        )
        return result + f"\n（当前已写至：{st[:60]}；请按模板写下一节，勿重复已写章节。）"

    @tool
    def write_table_to_docx(
        headers: list[str], rows: list[list[str]], caption: str = ""
    ) -> str:
        """在 Word 中插入三线表。headers: 表头字符串列表；rows: 数据行列表，每行列数须与 headers 一致，不足用空字符串补齐；caption: 表标题，如「表2-1 系统参与者词汇表」。"""
        progress_path = get_progress_path(ctx.docx_path)
        _, written_tables = get_written_set(progress_path)
        cap = (caption or "").strip()
        if cap and cap in written_tables:
            return f"该表已写入：「{cap}」。请写下一节或下一张表，勿重复。"

        ctx.word_builder, ctx.docx_path = ensure_word_builder(
            ctx.word_builder, ctx.docx_path, ctx.existing_docx_text
        )
        return write_table_into_docx(
            ctx.word_builder,
            ctx.docx_path,
            headers,
            rows,
            caption=cap or None,
            progress_path=progress_path,
        )

    @tool
    def write_figure_caption_to_docx(caption: str) -> str:
        """写入图片题注，如「图3-1 系统架构图」。用于图题场景，避免走正文工具导致样式错误。"""
        ctx.word_builder, ctx.docx_path = ensure_word_builder(
            ctx.word_builder, ctx.docx_path, ctx.existing_docx_text
        )
        progress_path = get_progress_path(ctx.docx_path)
        return write_figure_caption_into_docx(
            ctx.word_builder, ctx.docx_path, caption, progress_path=progress_path
        )

    @tool
    def validate_docx(docx_path: str) -> str:
        """验证 Word 文档：检查是否全部黑色字体、是否含有思考内容。全部章节写完后必须调用此工具验证。参数 docx_path: docx 文件路径。"""
        p = Path(docx_path)
        if not p.is_absolute():
            p = ctx.docx_path.parent / p
        result, ctx.validated_ok = validate_docx_path_with_ok(p)
        return result

    return [
        search_materials,
        read_format_spec,
        read_chapter_spec,
        debug_chapter_spec_tool,
        run_terminal_command,
        write_section_to_docx,
        write_table_to_docx,
        write_figure_caption_to_docx,
        validate_docx,
    ]
