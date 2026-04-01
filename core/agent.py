"""LangChain Agent：使用 deepagents 的 create_deep_agent 构建论文生成 Agent（支持 Skills）。"""
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend

from core.context import (
    format_agent_runtime_context,
    get_config_profile_name,
    load_system_prompt_content,
    load_template_content,
)
from core.llm import get_writer_llm
from core.rag import get_or_build_vectorstore
from tools.langchain_tools import ThesisContext, create_thesis_tools


def _build_system_message(
    *,
    user: str | None = None,
    docx_path: Path | None = None,
) -> str:
    """构建系统提示词。只放基本角色、模板结构和写作规则。"""
    prof = get_config_profile_name()
    system_prompt = load_system_prompt_content()
    template = load_template_content()
    runtime = format_agent_runtime_context(prof, user=user, docx_path=docx_path)

    print("===== 已加载提示词 =====")
    print(f"  · 模板包: config/{prof}/")
    print(f"  · system_prompt: {len(system_prompt)} 字")
    print(f"  · template: {len(template)} 字")
    print("  · skills/chapters: 由 deepagents skills + 工具按需读取")

    return f"""你是一个专业的毕业论文撰写助手。你将根据素材、论文结构模板和格式要求，逐章撰写完整论文并写入 Word 文档。

**当前论文配置模板包：{prof}**（config/{prof}/）

## 当前运行环境与相关文件（虚拟路径索引）

{runtime}

下文「用户总指示」「论文结构模板」已从磁盘加载并注入；**无需**再用 `read_file` 重复读取 `system_prompt.md`、`template.md`，除非用户明确要求核对原文。

## 写作流程（严格遵守，每章都要执行）

1. **读取章节规范**：调用 `read_chapter_spec` 读取该章的内容要求与结构细则。
2. **读取格式要求**：优先通过已加载的 deepagent skills（`format-rules`）按需读取格式规则文件，不再走固定工具路由。
3. **搜索素材（控制频率）**：在进入“某一章”时调用 `search_materials` 做 **1 次** 面向整章的检索并做笔记（不要为每个小节反复检索）。
   只有当你发现“缺少关键信息/证据/术语定义/模块细节”时，才允许对该缺口再做 **补充检索**。
4. **逐节写入**：根据素材和规范，调用 `write_section_to_docx` 将标题和正文写入 Word。
5. **插入表格**：需要展示结构化数据时，调用 `write_table_to_docx` 插入三线表。
6. **插入图题**：需要图片题注时，调用 `write_figure_caption_to_docx`。
7. **验证文档**：全部章节写完后，调用 `validate_docx` 验证，通过后才能结束。
8. **顺序执行**：按模板顺序从摘要开始，逐节写入。不要跳章、不要重复已写章节。

## 写作规则

- **禁止编写参考文献**：不得写入「参考文献」标题或任何文献列表，由用户自行完成。
- **禁止捏造数据**：不得出现具体夸张数据（如 99%、提升 50% 等），统一模糊处理。
- **禁止元内容**：正文中不得包含思考过程、"我认为"、"接下来"等元内容。
- **表格规范**：多行多列数据必须用 `write_table_to_docx` 写入，禁止 Markdown 表格语法。
- **图题规范**：图题必须用 `write_figure_caption_to_docx` 写入。
- **基于素材**：每节内容必须基于 `search_materials` 检索到的素材撰写，不得凭空捏造。
- **分段写入**：正文中用换行符分隔段落，系统自动处理为 Word 独立段落。
- **禁止重复**：根据工具返回的「当前已写至」判断进度，只写尚未写入的下一节。
- **写前自检（强制）**：每次调用任一写入工具前，必须先在心中完成一次“内容+样式”检查：
  1) 当前要写的目标标题是否与 PlanAgent 的 NextTarget 完全一致（不得改名、不得越级）；
  2) 当前内容类型是否正确（正文/三线表/图题）并选择了正确工具；
  3) 样式是否符合规范（标题层级、字号、段落规则、图题居中、表格走三线表工具）；
  4) 如检查失败，先修正文案或改用正确工具，再写入。

## 用户总指示

{system_prompt}

## 论文结构模板

{template}

（素材通过 search_materials 按需检索；格式要求通过 skills 按需读取；章节规范通过 read_chapter_spec 按需读取。不要跳过这些步骤。）"""


def build_agent(
    user: str,
    materials_text: str,
    docx_path: Path,
    existing_docx_text: str | None = None,
    *,
    streaming: bool = True,
):
    """构建论文生成 LangChain Agent（基于 deepagents）。

    流程：
    1. 将素材构建/加载为 RAG 向量库
    2. 创建共享状态与 LangChain 工具
    3. 使用 deepagents 的 create_deep_agent 组装 Agent（加载 skills）
    """
    print("[Agent] 构建/加载 RAG 向量库...")
    vectorstore = get_or_build_vectorstore(materials_text, user)

    ctx = ThesisContext(
        docx_path=docx_path,
        existing_docx_text=existing_docx_text,
        vectorstore=vectorstore,
    )
    tools = create_thesis_tools(ctx)

    llm = get_writer_llm(streaming=streaming)
    system_message = _build_system_message(user=user, docx_path=docx_path)
    project_root = Path(__file__).resolve().parent.parent
    prof = get_config_profile_name()
    skill_source = f"/config/{prof}/skills/"
    skill_dir = project_root / "config" / prof / "skills"
    skills = [skill_source] if skill_dir.exists() else None
    if skills:
        print(f"[Agent] 已启用 Skills：{skill_source}")
    else:
        print(f"[Agent] 未找到 Skills 目录，跳过加载：{skill_source}")

    agent = create_deep_agent(
        model=llm,
        tools=tools,
        system_prompt=system_message,
        backend=FilesystemBackend(root_dir=str(project_root), virtual_mode=True),
        skills=skills,
        # temperature=0.3,
    )
    return agent
