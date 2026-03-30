from core.context import get_chapter_spec_path, get_chapters_spec_dir


def debug_chapter_spec(title: str) -> str:
    """查看章节标题与规范 md 的映射及存在情况，返回可打印文本（供命令行/测试使用）。"""
    lines: list[str] = [f"[调试] 章节标题：{title!r}"]
    path = get_chapter_spec_path(title)
    if path is None:
        lines.append("[调试] 未找到对应规范文件。")
        lines.append(
            f"[调试] 请检查当前模板包下 chapters 目录中的 md 文件名是否与标题规则一致。目录：{get_chapters_spec_dir()}"
        )
        return "\n".join(lines)
    lines.append(f"[调试] 规范文件路径：{path}")
    try:
        first_lines = path.read_text(encoding="utf-8").splitlines()[:5]
        if first_lines:
            lines.append("[调试] 文件前几行：")
            lines.extend("  " + line for line in first_lines)
    except Exception as e:
        lines.append(f"[调试] 读取文件内容失败：{e}")
    return "\n".join(lines)

