"""
论文生成 CLI 入口（基于 LangChain + RAG）。

用法：
  uv run main.py                                # 交互式选择模板和学生
  uv run main.py --profile 软件学院 --user 张三   # 直接指定
  uv run main.py --list-profiles                 # 列出可用模板包
  uv run main.py --no-stream                     # 关闭终端流式输出

流程：
  第一步：从 data/input/{user} 提取素材到 data/extracted/{user}（已存在则跳过）
  第二步：将素材向量化存储（RAG），LangChain Agent 逐章生成论文到 output/{user}.docx
"""
import argparse
import re
import shutil
from pathlib import Path

from core.context import (
    extract_all_docx,
    get_config_profile_name,
    get_extracted_dir,
    list_config_profiles,
    list_extracted_files,
    list_input_docx_files,
    list_input_md_sql_files,
    load_template_content,
    read_all_materials_from_extracted,
    set_config_profile,
    sync_md_sql_to_extracted,
)
from core.extract_docx import read_docx_to_text

MATERIAL_INPUT_DIR = Path(__file__).resolve().parent / "data" / "input"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"


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
    """以流式方式运行 Agent：终端逐 token 输出模型回复，并打印图节点进度；返回最后一条助手消息摘要。"""
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


def _format_plan_block(
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


def select_user_interactive() -> str:
    """交互式选择或输入学生姓名。"""
    if MATERIAL_INPUT_DIR.exists():
        users = sorted(d.name for d in MATERIAL_INPUT_DIR.iterdir() if d.is_dir())
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


def run_step1(user: str) -> bool:
    """第一步：Word → Markdown，并同步 .md/.sql 到 extracted。若已有素材则跳过。"""
    input_dir = MATERIAL_INPUT_DIR / user
    existing = list_extracted_files(user)
    if existing:
        print(f"[第一步] 已存在素材（{len(existing)} 个文件），跳过提取。")
        return True

    docx_files = list_input_docx_files(input_dir)
    md_sql_files = list_input_md_sql_files(input_dir)
    if docx_files:
        print(f"[第一步] 提取 Word + 同步 .md/.sql → data/extracted/{user} …")
        extract_all_docx(input_dir=input_dir, output_dir=get_extracted_dir() / user)
    if md_sql_files:
        print(f"[第一步] 同步 .md/.sql → data/extracted/{user} …")
        sync_md_sql_to_extracted(user)
    else:
        print(f"[第一步] 未找到素材：请在 {input_dir} 放入 .docx、.md 或 .sql。")
        return False

    print("[第一步] 完成。")
    return True


def run_step2(user: str, *, stream: bool = True, auto_repair: bool = True) -> None:
    """第二步：RAG 存储素材 + LangChain Agent 生成论文。"""
    from core.agent import build_agent
    from tools.thesis_tools import get_written_set
    from tools.thesis_tools import get_progress_path
    from tools.langchain_tools import get_expected_section_order
    from tools.langchain_tools import _normalize_title_for_compare as normalize_title_for_compare
    from tools.word_tools import truncate_docx_from_heading, truncate_progress_from_section
    from core.plan_agent import PlanAgent

    materials_full = read_all_materials_from_extracted(user)
    if not materials_full.strip():
        print(f"[第二步] 未找到素材，请先完成第一步。")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    docx_path = OUTPUT_DIR / f"{user}.docx"
    docx_path_abs = str(docx_path.resolve()).replace("\\", "/")

    existing_docx_text = None
    last_written = None
    progress_path = OUTPUT_DIR / f"{user}.progress.txt"

    if docx_path.exists():
        existing_docx_text = read_docx_to_text(docx_path)
        print(f"[第二步] 续写模式：已读取已写论文（{len(existing_docx_text)} 字）。")
        if progress_path.exists():
            with open(progress_path, "r", encoding="utf-8") as f:
                lines = [ln.strip() for ln in f if ln.strip()]
            if lines:
                for ln in reversed(lines):
                    if "\t" not in ln:
                        continue
                    kind, title = ln.split("\t", 1)
                    if kind == "section":
                        last_written = title.strip()
                        break
                if last_written:
                    print(f"[第二步] 上次已写至：「{last_written}」")

    expected_order_norm, expected_norm_to_raw = get_expected_section_order()

    # 依据 chapters+progress，判断是否存在“后写了更后面的内容，导致顺序错乱”
    written_sections, _ = get_written_set(progress_path)
    written_norm = {normalize_title_for_compare(t) for t in written_sections if t}
    missing_norm = [n for n in expected_order_norm if n not in written_norm]

    # 自动修复（截断错误/多余部分）：把从“最早的错乱后置标题”开始的 docx + progress 截断，
    # 让后续补写时不会继续追加到错误位置。
    if (
        auto_repair
        and docx_path.exists()
        and progress_path.exists()
        and missing_norm
    ):
        first_missing_idx = expected_order_norm.index(missing_norm[0])
        expected_idx_map = {n: i for i, n in enumerate(expected_order_norm)}
        # written_norm 可能包含模板外的标题（例如正文里额外写入的层级/表述），
        # 这时不能直接用 expected_order_norm.index(n) 否则会抛 ValueError。
        out_of_order_written = [
            n
            for n in written_norm
            if n in expected_idx_map and expected_idx_map[n] > first_missing_idx
        ]
        if out_of_order_written:
            truncate_idx = min(expected_idx_map[n] for n in out_of_order_written)
            truncate_norm = expected_order_norm[truncate_idx]
            truncate_title_actual = next(
                (t for t in written_sections if normalize_title_for_compare(t) == truncate_norm),
                None,
            )
            if truncate_title_actual:
                bak_docx = docx_path.with_suffix(docx_path.suffix + ".bak")
                bak_progress = progress_path.with_suffix(progress_path.suffix + ".bak")
                if not bak_docx.exists():
                    shutil.copy2(docx_path, bak_docx)
                if not bak_progress.exists():
                    shutil.copy2(progress_path, bak_progress)

                ok1 = truncate_docx_from_heading(docx_path, truncate_title_actual)
                ok2 = truncate_progress_from_section(progress_path, truncate_title_actual)
                if ok1 and ok2:
                    print(
                        f"[自动修复] 检测到顺序错乱，已截断：从《{truncate_title_actual}》开始。已备份到 {bak_docx.name} / {bak_progress.name}。"
                    )
                    existing_docx_text = read_docx_to_text(docx_path)
                    last_written = None
                    written_sections, _ = get_written_set(progress_path)
                    written_norm = {normalize_title_for_compare(t) for t in written_sections if t}
                    missing_norm = [n for n in expected_order_norm if n not in written_norm]

    # missing_titles 的计算不再放在 main.py：由 PlanAgent 根据 template/chapters + progress.txt 自己生成

    plan_agent = PlanAgent(max_items_per_round=1)

    agent = build_agent(
        user=user,
        materials_text=materials_full,
        docx_path=docx_path,
        existing_docx_text=existing_docx_text,
        streaming=stream,
    )

    cfg = {"recursion_limit": 150}
    print("[第二步] 正在生成论文（LangChain Agent + RAG，自动续写模式）…")

    max_rounds = 10  # 避免无限循环；写到后面一般 2~4 轮足够
    last_missing: list[str] = []
    plan_log_path = OUTPUT_DIR / f"{user}.plan.txt"
    for round_idx in range(1, max_rounds + 1):
        # 动态读取进度文件，便于多轮续写
        if progress_path.exists():
            with open(progress_path, "r", encoding="utf-8") as f:
                lines = [ln.strip() for ln in f if ln.strip()]
            if lines:
                for ln in reversed(lines):
                    if "\t" not in ln:
                        continue
                    kind, title = ln.split("\t", 1)
                    if kind == "section":
                        last_written = title.strip()
                        break

        plan_steps, missing_titles = plan_agent.plan_for_user(progress_path)
        if not missing_titles:
            print(f"[第二步] 期望标题已全部写完（第 {round_idx} 轮）。")
            break

        # 仍缺少章节时，使用 PlanAgent 制定本轮“下一缺失标题”（并只允许写这个）
        last_missing = missing_titles
        if not plan_steps:
            print(f"[PlanAgent] 第 {round_idx} 轮未给出可执行 steps，提前结束。")
            break
        target = plan_steps[0].title
        plan_text = "\n".join([f"- {s.title}（{s.reason}）" for s in plan_steps])
        print(
            f"\n[第二步] 第 {round_idx} 轮：仍缺少标题：{', '.join(missing_titles[:6])}"
            + ("…" if len(missing_titles) > 6 else "")
        )
        plan_block = _format_plan_block(
            round_idx=round_idx,
            max_rounds=max_rounds,
            last_written=last_written,
            missing_titles=missing_titles,
            plan_steps=plan_steps,
        )
        print(plan_block)
        with open(plan_log_path, "a", encoding="utf-8") as f:
            f.write(plan_block + "\n")

        if existing_docx_text:
            user_message = (
                f'【续写】当前文档已存在，请从进度接着写，不要重写已有章节。'
                f'请先补全下一缺失标题：{target}。'
                f'本轮只允许写入这个标题：{target}；其他标题禁止写入。'
                f'在写入该缺失标题之前，不要写入更后面的任何标题。'
                f'\n【写前自检（每次写入前必须执行）】'
                f'\n1) 你当前写入的标题必须等于：{target}'
                f'\n2) 先判断写入类型：正文=write_section_to_docx；表格=write_table_to_docx；图题=write_figure_caption_to_docx'
                f'\n3) 再检查样式要求：标题层级/段落/图题居中/表格三线表。'
                f'\n\n【本轮计划（不可跳过）】\n{plan_text}\n'
                f'validate_docx 路径："{docx_path_abs}"。'
            )
            if last_written:
                user_message = (
                    f"【续写】上次已写至：「{last_written}」。请从该节之后继续写入，不要重写已有章节。\n\n"
                    + user_message
                )
        else:
            user_message = (
                f'【从头开始】请按论文结构模板从摘要开始撰写。'
                f'请先补全下一缺失标题：{target}。'
                f'本轮只允许写入这个标题：{target}；其他标题禁止写入。'
                f'在写入该缺失标题之前，不要写入更后面的任何标题。'
                f'\n【写前自检（每次写入前必须执行）】'
                f'\n1) 你当前写入的标题必须等于：{target}'
                f'\n2) 先判断写入类型：正文=write_section_to_docx；表格=write_table_to_docx；图题=write_figure_caption_to_docx'
                f'\n3) 再检查样式要求：标题层级/段落/图题居中/表格三线表。'
                f'\n\n【本轮计划（不可跳过）】\n{plan_text}\n'
                f'validate_docx 路径："{docx_path_abs}"。'
            )

        if stream:
            _ = run_agent_stream(agent, user_message, cfg)
        else:
            _result = agent.invoke({"messages": [("user", user_message)]}, cfg)

    if last_missing:
        print(
            f"\n[第二步] 注意：达到最大轮数 {max_rounds} 后仍未写完期望标题：{', '.join(last_missing)}。"
        )
    print(f"已保存：{docx_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="论文生成 CLI（基于 LangChain + RAG）"
    )
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        metavar="名称",
        help="模板包名（如 软件学院、智科）",
    )
    parser.add_argument(
        "--user",
        type=str,
        default=None,
        metavar="姓名",
        help="学生姓名（对应 data/input 下的子目录名）",
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="列出可用模板包后退出",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="关闭流式输出（整段返回后再显示，适合脚本日志）",
    )
    parser.add_argument(
        "--no-auto-repair",
        action="store_true",
        help="关闭自动截断修复乱序追加（会破坏文档顺序时使用）。",
    )
    args = parser.parse_args()

    if args.list_profiles:
        names = list_config_profiles()
        if not names:
            print("未找到任何模板包。")
        else:
            print("可用模板包：")
            for n in names:
                print(f"  - {n}")
        return

    if args.profile:
        set_config_profile(args.profile)
    else:
        profile = select_profile_interactive()
        set_config_profile(profile)
    print(f"[配置] 论文模板包：{get_config_profile_name()}")

    user = args.user or select_user_interactive()
    if not user:
        print("未指定学生姓名。")
        return
    print(f"[配置] 学生：{user}")

    if run_step1(user):
        run_step2(user, stream=not args.no_stream, auto_repair=not args.no_auto_repair)


if __name__ == "__main__":
    main()
