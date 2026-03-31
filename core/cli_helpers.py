"""CLI 辅助函数：交互选择、流式输出、计划展示。"""

from __future__ import annotations

import re
from pathlib import Path

from core.context import list_config_profiles


def _print_llm_chunk_content(msg_chunk) -> None:
    """打印流式 LLM 片段中的文本（兼容 str / 多模态 list）。"""
    c = getattr(msg_chunk, "content", None)
    if not c:
        return
    if isinstance(c, str):
        print(c, end="", flush=True)
        return
    if isinstance(c, list):
        for part in c:
            if isinstance(part, dict) and part.get("type") == "text":
                print(part.get("text") or "", end="", flush=True)


def run_agent_stream(agent, user_message: str, config: dict) -> str:
    """以流式方式运行 Agent，并返回最后一条助手消息内容摘要。"""
    input_data = {"messages": [("user", user_message)]}
    stream_modes = ["messages", "updates", "values"]
    last_messages = None
    print("\n---------- 流式输出（模型 + 步骤）----------\n", flush=True)
    for mode, payload in agent.stream(input_data, config, stream_mode=stream_modes):
        if mode == "messages":
            msg_chunk, _meta = payload
            _print_llm_chunk_content(msg_chunk)
            tcs = getattr(msg_chunk, "tool_calls", None) or []
            for tc in tcs:
                if isinstance(tc, dict):
                    name = tc.get("name", "")
                else:
                    name = getattr(tc, "name", "") or ""
                if name:
                    print(f"\n[调用工具] {name}", flush=True)
        elif mode == "updates":
            for node_name, _data in payload.items():
                if node_name.startswith("__"):
                    continue
                print(f"\n── 步骤完成: {node_name} ──", flush=True)
        elif mode == "values":
            if isinstance(payload, dict) and "messages" in payload:
                last_messages = payload["messages"]
    print("\n\n---------- 本轮结束 ----------\n", flush=True)
    if last_messages:
        final = last_messages[-1]
        content = getattr(final, "content", None) or ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                p.get("text", "") if isinstance(p, dict) else str(p) for p in content
            )
    return ""


def format_plan_block(
    *,
    round_idx: int,
    max_rounds: int,
    last_written: str | None,
    missing_titles: list[str],
    plan_steps,
) -> str:
    """格式化可读的本轮计划块（便于终端查看与落盘）。"""
    target = plan_steps[0].title if plan_steps else "（无）"
    lines = [
        "",
        "=" * 62,
        f"[PLAN] Round {round_idx}/{max_rounds}",
        f"[PLAN] LastWritten: {last_written or '（无）'}",
        f"[PLAN] MissingTotal: {len(missing_titles)}",
        f"[PLAN] NextTarget: {target}",
        "[PLAN] Steps:",
    ]
    if plan_steps:
        for i, s in enumerate(plan_steps, 1):
            lines.append(f"  {i}. {s.title}")
            lines.append(f"     - 原因: {s.reason}")
    else:
        lines.append("  1. （无可执行步骤）")
    lines.append("[PLAN] Constraints:")
    lines.append("  - 本轮只允许写入 NextTarget")
    lines.append("  - 不得写入更后面的标题")
    lines.append("  - 如信息不足，再补充一次检索")
    lines.append("=" * 62)
    return "\n".join(lines)


def chapter_bucket_from_title(title: str) -> str:
    """将标题归入章节桶：前置部分 / 第N章。"""
    t = (title or "").strip()
    m_top = re.match(r"^第(\d+)章", t)
    if m_top:
        return f"第{m_top.group(1)}章"
    m_sub = re.match(r"^(\d+)\.", t)
    if m_sub:
        return f"第{m_sub.group(1)}章"
    return "前置部分"


def select_profile_interactive() -> str:
    """交互式选择论文模板包。"""
    profiles = list_config_profiles()
    if not profiles:
        raise FileNotFoundError(
            "未找到任何模板包（config 下需有子目录含 template.md 与 system_prompt.md）。"
        )
    if len(profiles) == 1:
        print(f"[配置] 仅有一个模板包，自动选用：{profiles[0]}")
        return profiles[0]

    print("\n可用论文模板包：")
    for i, name in enumerate(profiles, 1):
        print(f"  {i}. {name}")

    while True:
        choice = input("\n请选择模板编号：").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(profiles):
            return profiles[int(choice) - 1]
        print("无效输入，请重新选择。")


def select_user_interactive(material_input_dir: Path) -> str:
    """交互式选择或输入学生姓名。"""
    if material_input_dir.exists():
        users = sorted(d.name for d in material_input_dir.iterdir() if d.is_dir())
        if users:
            print("\n已有素材目录：")
            for i, name in enumerate(users, 1):
                print(f"  {i}. {name}")
            choice = input("\n请选择编号或直接输入新用户名：").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(users):
                return users[int(choice) - 1]
            if choice:
                return choice
    return input("请输入学生姓名：").strip()
