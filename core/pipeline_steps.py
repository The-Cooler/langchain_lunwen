"""论文生成流水线步骤：step1/step2。"""

from __future__ import annotations

import shutil
from pathlib import Path

from core.cli_helpers import chapter_bucket_from_title, format_plan_block, run_agent_stream
from core.context import (
    extract_all_docx,
    get_extracted_dir,
    list_extracted_files,
    list_input_docx_files,
    list_input_md_sql_files,
    read_all_materials_from_extracted,
    sync_md_sql_to_extracted,
)
from core.extract_docx import read_docx_to_text

MATERIAL_INPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "input"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


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
    from core.plan_agent import PlanAgent
    from tools.langchain_tools import (
        _normalize_title_for_compare as normalize_title_for_compare,
    )
    from tools.langchain_tools import get_expected_section_order
    from tools.thesis_tools import get_written_set
    from tools.word_tools import truncate_docx_from_heading, truncate_progress_from_section

    materials_full = read_all_materials_from_extracted(user)
    if not materials_full.strip():
        print("[第二步] 未找到素材，请先完成第一步。")
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
            lines = [ln.strip() for ln in progress_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
            for ln in reversed(lines):
                if "\t" not in ln:
                    continue
                kind, title = ln.split("\t", 1)
                if kind == "section":
                    last_written = title.strip()
                    break
            if last_written:
                print(f"[第二步] 上次已写至：「{last_written}」")

    expected_order_norm, _expected_norm_to_raw = get_expected_section_order()
    written_sections, _ = get_written_set(progress_path)
    written_norm = {normalize_title_for_compare(t) for t in written_sections if t}
    missing_norm = [n for n in expected_order_norm if n not in written_norm]

    if auto_repair and docx_path.exists() and progress_path.exists() and missing_norm:
        first_missing_idx = expected_order_norm.index(missing_norm[0])
        expected_idx_map = {n: i for i, n in enumerate(expected_order_norm)}
        out_of_order_written = [
            n for n in written_norm if n in expected_idx_map and expected_idx_map[n] > first_missing_idx
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

    plan_agent = PlanAgent(max_items_per_round=1)
    cfg = {"recursion_limit": 150}
    print("[第二步] 正在生成论文（LangChain Agent + RAG，自动续写模式）…")

    max_rounds = 10
    last_missing: list[str] = []
    plan_log_path = OUTPUT_DIR / f"{user}.plan.txt"
    chapter_agent = None
    active_bucket: str | None = None

    for round_idx in range(1, max_rounds + 1):
        if progress_path.exists():
            lines = [ln.strip() for ln in progress_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
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
        last_missing = missing_titles
        if not plan_steps:
            print(f"[PlanAgent] 第 {round_idx} 轮未给出可执行 steps，提前结束。")
            break

        target = plan_steps[0].title
        target_bucket = chapter_bucket_from_title(target)
        if chapter_agent is None or active_bucket != target_bucket:
            existing_docx_text = read_docx_to_text(docx_path) if docx_path.exists() else None
            print(f"[第二步] 切换到 {target_bucket}：创建新的 Agent 会话。")
            chapter_agent = build_agent(
                user=user,
                materials_text=materials_full,
                docx_path=docx_path,
                existing_docx_text=existing_docx_text,
                streaming=stream,
            )
            active_bucket = target_bucket

        plan_text = "\n".join([f"- {s.title}（{s.reason}）" for s in plan_steps])
        print(
            f"\n[第二步] 第 {round_idx} 轮：仍缺少标题：{', '.join(missing_titles[:6])}"
            + ("…" if len(missing_titles) > 6 else "")
        )
        plan_block = format_plan_block(
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
                f"【续写】当前文档已存在，请从进度接着写，不要重写已有章节。"
                f"请先补全下一缺失标题：{target}。"
                f"本轮只允许写入这个标题：{target}；其他标题禁止写入。"
                f"在写入该缺失标题之前，不要写入更后面的任何标题。"
                f"\n【写前自检（每次写入前必须执行）】"
                f"\n1) 你当前写入的标题必须等于：{target}"
                f"\n2) 先判断写入类型：正文=write_section_to_docx；表格=write_table_to_docx；图题=write_figure_caption_to_docx"
                f"\n3) 再检查样式要求：标题层级/段落/图题居中/表格三线表。"
                f"\n\n【本轮计划（不可跳过）】\n{plan_text}\n"
                f'validate_docx 路径："{docx_path_abs}"。'
            )
            if last_written:
                user_message = (
                    f"【续写】上次已写至：「{last_written}」。请从该节之后继续写入，不要重写已有章节。\n\n"
                    + user_message
                )
        else:
            user_message = (
                f"【从头开始】请按论文结构模板从摘要开始撰写。"
                f"请先补全下一缺失标题：{target}。"
                f"本轮只允许写入这个标题：{target}；其他标题禁止写入。"
                f"在写入该缺失标题之前，不要写入更后面的任何标题。"
                f"\n【写前自检（每次写入前必须执行）】"
                f"\n1) 你当前写入的标题必须等于：{target}"
                f"\n2) 先判断写入类型：正文=write_section_to_docx；表格=write_table_to_docx；图题=write_figure_caption_to_docx"
                f"\n3) 再检查样式要求：标题层级/段落/图题居中/表格三线表。"
                f"\n\n【本轮计划（不可跳过）】\n{plan_text}\n"
                f'validate_docx 路径："{docx_path_abs}"。'
            )

        if stream:
            _ = run_agent_stream(chapter_agent, user_message, cfg)
        else:
            _ = chapter_agent.invoke({"messages": [("user", user_message)]}, cfg)

    if last_missing:
        print(f"\n[第二步] 注意：达到最大轮数 {max_rounds} 后仍未写完期望标题：{', '.join(last_missing)}。")
    print(f"已保存：{docx_path}")
