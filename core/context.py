"""
论文编写上下文：多份 Word 提取结果、模板、system_prompt、SKILL。
配置按「模板包」子目录划分：config/{profile}/ 下含 template.md、system_prompt.md、skill/、chapters/。
流程：从 data/input 多份 Word 提取数据 → 根据所选 profile 的模板 + 提取结果 + system_prompt + skill 做论文。
"""
from pathlib import Path

from core.extract_docx import EXTRACTED_DIR, INPUT_DOCX_DIR, list_input_docx, run_extract

_ROOT = Path(__file__).resolve().parent.parent
_DIR_CONFIG = _ROOT / "config"

# 当前选用的模板包名称（如「软件学院」「智科」），由 set_config_profile 或首次访问时默认解析
_active_profile: str | None = None


def list_config_profiles() -> list[str]:
    """列出 config 下可作为论文模板的子目录名（须含 template.md 与 system_prompt.md）。"""
    if not _DIR_CONFIG.is_dir():
        return []
    names: list[str] = []
    for p in sorted(_DIR_CONFIG.iterdir()):
        if not p.is_dir():
            continue
        if (p / "template.md").is_file() and (p / "system_prompt.md").is_file():
            names.append(p.name)
    return names


def _default_profile_name() -> str:
    names = list_config_profiles()
    if not names:
        raise FileNotFoundError(
            f"未在 {_DIR_CONFIG} 下找到任何论文配置目录（子目录内需含 template.md 与 system_prompt.md）"
        )
    if "软件学院" in names:
        return "软件学院"
    return names[0]


def set_config_profile(name: str) -> None:
    """
    设置当前论文配置模板包（config 下的子目录名）。
    要求：存在 template.md、system_prompt.md、skill/论文助手.md、chapters/ 目录。
    """
    global _active_profile
    d = _DIR_CONFIG / name
    if not d.is_dir():
        raise FileNotFoundError(f"配置模板目录不存在：{d}")
    if not (d / "template.md").is_file():
        raise FileNotFoundError(f"缺少 template.md：{d}")
    if not (d / "system_prompt.md").is_file():
        raise FileNotFoundError(f"缺少 system_prompt.md：{d}")
    skill_dir = d / "skill"
    if not skill_dir.is_dir() or not (skill_dir / "论文助手.md").is_file():
        raise FileNotFoundError(f"缺少 skill/论文助手.md：{d}")
    chapters = d / "chapters"
    if not chapters.is_dir():
        raise FileNotFoundError(f"缺少 chapters 目录：{d}")
    _active_profile = name


def get_config_profile_name() -> str:
    """当前模板包名称；未设置时自动选用默认（优先 软件学院）。"""
    global _active_profile
    if _active_profile is None:
        set_config_profile(_default_profile_name())
    return _active_profile


def get_config_profile_dir() -> Path:
    """当前模板包根目录：config/{profile}/"""
    return _DIR_CONFIG / get_config_profile_name()


def get_project_root() -> Path:
    return _ROOT


def get_input_docx_dir() -> Path:
    """放多份 Word 的目录。"""
    return INPUT_DOCX_DIR


def get_extracted_dir() -> Path:
    """提取结果目录（每份 Word 对应一个 .md）。"""
    return EXTRACTED_DIR


def get_template_path() -> Path:
    return get_config_profile_dir() / "template.md"


def get_system_prompt_path() -> Path:
    return get_config_profile_dir() / "system_prompt.md"


def get_skill_dir() -> Path:
    return get_config_profile_dir() / "skill"


def get_skill_path() -> Path:
    return get_skill_dir() / "论文助手.md"


def get_skill_index_path() -> Path:
    return get_skill_dir() / "论文要求-索引.md"


def get_chapters_spec_dir() -> Path:
    """当前模板包下的章节规范目录。"""
    return get_config_profile_dir() / "chapters"


def _chapter_title_to_basename(section_title: str) -> str:
    """将章节标题转为规范 md 文件名（不含扩展名）。"""
    import re

    s = section_title.strip()
    s = re.sub(r"第\s*(\d+)\s*章", r"第\1章", s)
    s = re.sub(r'[<>:"/\\|?*]', "-", s).replace(" ", "-")
    s = re.sub(r"-+", "-", s).strip("-")[:60].strip("-")
    return s or "未命名"


def get_chapter_spec_path(section_title: str) -> Path | None:
    """根据章节标题返回对应规范 md 路径；无则返回 None。"""
    if not section_title or not section_title.strip():
        return None
    name = _chapter_title_to_basename(section_title)
    path = get_chapters_spec_dir() / f"{name}.md"
    return path if path.exists() else None


def load_template_content() -> str:
    return get_template_path().read_text(encoding="utf-8")


def load_system_prompt_content() -> str:
    return get_system_prompt_path().read_text(encoding="utf-8")


def load_skill_content(include_index: bool = True) -> str:
    text = get_skill_path().read_text(encoding="utf-8")
    if include_index and get_skill_index_path().exists():
        prof = get_config_profile_name()
        text += f"\n\n---\n按需查阅格式要求分章：config/{prof}/skill/论文要求-索引.md"
    return text


# 论文要求分章文件名（与索引一致），一次性全部读入 system，避免只读索引导致缺格式
SKILL_CHAPTER_NAMES = [
    "论文要求-索引.md",
    "论文要求-页面设置.md",
    "论文要求-字体与字号.md",
    "论文要求-段落与排版.md",
    "论文要求-其他要求.md",
]


def load_skill_full_content() -> str:
    """加载 论文助手.md + 全部论文要求分章内容，供 system 注入（不再只读索引）。"""
    parts = [get_skill_path().read_text(encoding="utf-8")]
    skill_dir = get_skill_dir()
    for name in SKILL_CHAPTER_NAMES:
        path = skill_dir / name
        if path.exists():
            parts.append(f"\n\n---\n# {name}\n\n{path.read_text(encoding='utf-8')}")
    return "".join(parts)


def list_input_docx_files(input_dir: Path | None = None) -> list[Path]:
    """列出待提取的 Word 文件。input_dir 不传则用默认 data/input。"""
    return list_input_docx(input_dir)


def list_extracted_files(extracted_subdir: str | Path | None = None) -> list[Path]:
    """列出已提取的素材文件（.md 与 .sql）。extracted_subdir 不传则列 data/extracted 下全部。"""
    base = EXTRACTED_DIR / extracted_subdir if extracted_subdir is not None else EXTRACTED_DIR
    if not base.exists():
        return []
    return sorted(list(base.glob("*.md")) + list(base.glob("*.sql")))


def read_all_materials_from_extracted(extracted_subdir: str | None = None) -> str:
    """读取 data/extracted（或 data/extracted/extracted_subdir）下全部 .md 与 .sql 的完整内容，不截断。"""
    extracted_dir = EXTRACTED_DIR
    if extracted_subdir:
        extracted_dir = extracted_dir / extracted_subdir
    if not extracted_dir.exists():
        return ""
    files = sorted(list(extracted_dir.glob("*.md")) + list(extracted_dir.glob("*.sql")))
    parts = []
    for f in files:
        content = f.read_text(encoding='utf-8')
        print(f"md{f.name}文字长度：{len(content)}")
        parts.append(f"## 来源：{f.name}\n\n{content}")
    return "\n\n---\n\n".join(parts) if parts else ""


def extract_all_docx(
    output_dir: Path | None = None,
    input_dir: Path | None = None,
) -> list[Path]:
    """从 input_dir 中所有 Word 提取到 output_dir，并同步 .md/.sql；返回生成/同步的文件列表。"""
    return run_extract(output_dir=output_dir, input_dir=input_dir)


def list_input_md_sql_files(input_dir: Path | None = None) -> list[Path]:
    """列出 input_dir 下所有 .md 和 .sql 文件。不传则用默认 data/input。"""
    from core.extract_docx import list_input_md_sql

    return list_input_md_sql(input_dir)


def sync_md_sql_to_extracted(user: str) -> list[Path]:
    """仅将 data/input/{user} 下的 .md 和 .sql 同步到 data/extracted/{user}（无 Word 时用）。"""
    from core.extract_docx import sync_md_sql_to_output

    input_dir = get_input_docx_dir() / user
    if not input_dir.exists():
        return []
    output_dir = EXTRACTED_DIR / user
    return sync_md_sql_to_output(input_dir, output_dir)


def get_writing_flow_instructions(user: str) -> str:
    """返回给 AI 的论文编写流程：基于多份 Word 提取结果 + 模板 + prompt + skill。"""
    prof = get_config_profile_name()
    return f"""# 论文编写流程（AI 按此执行）

1. **数据来源**：多份 Word 已提取到 `data/extracted/{user}`，每份 docx 对应一个 .md。按需读取这些 .md 作为写作素材。
2. **读取 system_prompt**：`config/{prof}/system_prompt.md` — 遵守用户总指示。
3. **读取 SKILL**：`config/{prof}/skill/论文助手.md`（及按需 `config/{prof}/skill/论文要求-*.md`）— 满足格式与字数要求。
4. **读取模板**：`config/{prof}/template.md` — 按此结构组织章节。
5. **根据模板 + 提取数据撰写**：用 data/extracted/{user} 中的内容填充各章，符合格式与字数；可用 `word_agent` 生成或润色 Word 文档。
"""
