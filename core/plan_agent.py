"""论文编写计划 Agent：通过 tool 读取 template/chapters/progress，再制定本轮计划。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from pydantic import BaseModel

from core.context import get_config_profile_name
from core.llm import get_llm
from tools.plan_tools import compute_missing_titles


@dataclass
class PlanStep:
    """本轮计划步骤。"""

    title: str
    reason: str


class _PlanStepItem(BaseModel):
    title: str
    reason: str


class _PlanOutput(BaseModel):
    """PlanAgent 的结构化输出。"""

    steps: List[_PlanStepItem]
    missing_titles: List[str]


class PlanAgent:
    """
    真正的 LangChain/LangGraph PlanAgent：
    - 内部使用 tool `compute_missing_titles` 读取 progress + 推导期望标题顺序（template+chapters）
    - 由 LLM 决定“下一步要补哪些缺失标题”（最多 N 个）
    - 输出必须符合 `_PlanOutput` schema
    """

    def __init__(self, max_items_per_round: int = 1) -> None:
        self.max_items_per_round = max_items_per_round

        self._llm = get_llm(streaming=False)

        # 关键点：你当前后端会拒绝 response_format/json_schema 类型，
        # 所以这里强制使用 function_calling 方式的 structured output，
        # 以避免任何手工 JSON 解析。
        self._structured_planner = self._llm.with_structured_output(
            _PlanOutput, method="function_calling"
        )

        self._prof = get_config_profile_name()

    def plan_for_user(self, progress_path: str | Path) -> Tuple[List[PlanStep], List[str]]:
        """对指定 progress_path 生成本轮计划，并返回 (plan_steps, missing_titles)。"""
        pp = Path(progress_path)

        # 通过工具读取进度并推导缺失标题（按期望顺序）。
        computed_missing_titles = compute_missing_titles.invoke(
            {"progress_path": pp.as_posix()}
        )
        if not isinstance(computed_missing_titles, list):
            computed_missing_titles = list(computed_missing_titles)

        system_prompt = f"""你是论文编写计划 Agent，当前模板包：{self._prof}。"""
        user_prompt = f"""
progress_path: {pp.as_posix()}

根据模板+chapters+progress，当前缺失标题（按期望顺序）如下：
{computed_missing_titles}

请在缺失标题列表中选择“下一步要补的标题”。
规则：
1. 不得重排顺序：steps 里的标题必须保持缺失列表的相对顺序
2. steps 数量最多为 {self.max_items_per_round}
3. 每个 steps 需要给出 title 与 reason（为什么要写它）
4. missing_titles 必须与上面提供的列表完全一致（不得增删改）
"""

        out = self._structured_planner.invoke(
            [("system", system_prompt), ("user", user_prompt)]
        )

        out_model = out if isinstance(out, _PlanOutput) else _PlanOutput.model_validate(out)
        # 如果模型意外改动 missing_titles，使用计算结果强制以避免“重复写入/跳写”。
        out_model = _PlanOutput(steps=out_model.steps, missing_titles=computed_missing_titles)
        steps = [PlanStep(title=s.title, reason=s.reason) for s in out_model.steps]
        return steps, out_model.missing_titles

