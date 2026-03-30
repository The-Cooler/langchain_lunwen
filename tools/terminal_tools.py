"""
终端命令工具：提供给 Agent 使用的 run_terminal_command。
"""

from __future__ import annotations

import subprocess


def run_terminal_command(command: str) -> str:
    """用于执行终端命令，返回标准输出或错误信息。"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
        )
    except Exception as e:
        return f"执行异常：{e}"

    if result.returncode == 0:
        return (result.stdout or "执行成功").strip()
    return (result.stderr or f"执行失败，返回码：{result.returncode}").strip()


def run_terminal_command_with_confirm(command: str) -> str:
    """执行前需人工确认（Y/N），用于排查规范文件等问题。"""
    confirm = input(f"\n即将执行终端命令：{command}\n是否继续？(Y/N) ")
    if confirm.lower() != "y":
        return "操作被用户取消"
    return run_terminal_command(command)

