"""论文写作计划相关工具（供 PlanAgent/其它模块调用）。"""

from __future__ import annotations

from pathlib import Path
from typing import List

from langchain_core.tools import tool

from tools.langchain_tools import _normalize_title_for_compare, get_expected_section_order
from tools.thesis_tools import get_written_set


@tool
def compute_missing_titles(progress_path: str) -> List[str]:
    """
    根据 progress.txt 计算缺失标题列表（按期望顺序）。

    progress_path: output/{user}.progress.txt 的路径。
    返回：缺失标题列表（已按期望顺序排序）。
    """
    expected_order_norm, expected_norm_to_raw = get_expected_section_order()
    pp = Path(progress_path)
    written_sections, _ = get_written_set(pp)
    written_norm = {_normalize_title_for_compare(t) for t in written_sections if t}
    missing_norm = [n for n in expected_order_norm if n not in written_norm]
    return [expected_norm_to_raw[n] for n in missing_norm]

