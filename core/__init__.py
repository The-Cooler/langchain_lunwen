"""论文编写核心模块（基于 LangChain + RAG）。

注意：core.agent 和 core.rag 不在此顶层导入，避免与 tools 产生循环依赖。
使用时请直接 from core.agent import build_agent。
"""
from core.context import (
    extract_all_docx,
    get_chapters_spec_dir,
    get_config_profile_name,
    get_extracted_dir,
    get_input_docx_dir,
    get_skill_path,
    get_system_prompt_path,
    get_template_path,
    get_writing_flow_instructions,
    list_config_profiles,
    list_extracted_files,
    list_input_docx_files,
    load_skill_content,
    load_system_prompt_content,
    load_template_content,
    set_config_profile,
)
from core.extract_docx import extract_one_docx, run_extract
from core.llm import get_llm

__all__ = [
    "get_llm",
    "get_input_docx_dir",
    "get_extracted_dir",
    "get_template_path",
    "get_system_prompt_path",
    "get_skill_path",
    "get_chapters_spec_dir",
    "get_config_profile_name",
    "list_config_profiles",
    "set_config_profile",
    "load_template_content",
    "load_system_prompt_content",
    "load_skill_content",
    "list_input_docx_files",
    "list_extracted_files",
    "extract_all_docx",
    "extract_one_docx",
    "run_extract",
    "get_writing_flow_instructions",
]
