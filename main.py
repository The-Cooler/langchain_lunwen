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

from core.cli_helpers import select_profile_interactive, select_user_interactive
from core.context import (
    get_config_profile_name,
    list_config_profiles,
    set_config_profile,
)
from core.pipeline_steps import MATERIAL_INPUT_DIR, run_step1, run_step2


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

    user = args.user or select_user_interactive(MATERIAL_INPUT_DIR)
    if not user:
        print("未指定学生姓名。")
        return
    print(f"[配置] 学生：{user}")

    if run_step1(user):
        run_step2(user, stream=not args.no_stream, auto_repair=not args.no_auto_repair)


if __name__ == "__main__":
    main()
