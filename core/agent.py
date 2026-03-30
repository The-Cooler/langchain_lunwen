"""LangChain Agent：使用 langgraph 的 create_react_agent 构建论文生成 Agent。

替代原 core/react_agent.py 中的手写 ReAct 循环，
改用 langgraph.prebuilt.create_react_agent（自带 tool_calling 支持）。
"""
from pathlib import Path

from langgraph.prebuilt import create_react_agent

from core.context import (
    get_config_profile_name,
    load_system_prompt_content,
    load_template_content,
)
from core.llm import get_llm
from core.rag import get_or_build_vectorstore
from tools.langchain_tools import ThesisContext, create_thesis_tools


def _build_system_message() -> str:
    """构建系统提示词。只放基本角色、模板结构和写作规则；素材和格式要求均由工具按需读取。"""
    prof = get_config_profile_name()
    system_prompt = load_system_prompt_content()
    template = load_template_content()

    print("===== 已加载提示词 =====")
    print(f"  · 模板包: config/{prof}/")
    print(f"  · system_prompt: {len(system_prompt)} 字")
    print(f"  · template: {len(template)} 字")
    print("  · skill/chapters: 由工具按需读取")

    return f"""你是一个专业的毕业论文撰写助手。你将根据素材、论文结构模板和格式要求，逐章撰写完整论文并写入 Word 文档。

**当前论文配置模板包：{prof}**（config/{prof}/）

## 写作流程（严格遵守，每章都要执行）

1. **读取章节规范**：调用 `read_chapter_spec` 读取该章的内容要求与结构细则。
2. **读取格式要求**：调用 `read_format_spec` 读取相关格式规范（如字体字号、段落排版等），首次写入前至少读取一次。
3. **搜索素材**：调用 `search_materials` 搜索该章节相关的素材关键词，获取写作依据。
4. **逐节写入**：根据素材和规范，调用 `write_section_to_docx` 将标题和正文写入 Word。
5. **插入表格**：需要展示结构化数据时，调用 `write_table_to_docx` 插入三线表。
6. **插入图题**：需要图片题注时，调用 `write_figure_caption_to_docx`。
7. **验证文档**：全部章节写完后，调用 `validate_docx` 验证，通过后才能结束。
8. **顺序执行**：按模板顺序从摘要开始，逐节写入。不要跳章、不要重复已写章节。

## 可用的格式规范类别（通过 read_format_spec 读取）

- `论文助手`：总体写作指引
- `页面设置`：页边距、装订线、页眉
- `字体与字号`：封面、摘要、目录、正文标题与内容、图表字体
- `段落与排版`：行距、缩进、段前段后、标点、表格/图/列表规则
- `其他要求`：关键词数量、用例与模块数量、图表编号

## 写作规则

- **禁止编写参考文献**：不得写入「参考文献」标题或任何文献列表，由用户自行完成。
- **禁止捏造数据**：不得出现具体夸张数据（如 99%、提升 50% 等），统一模糊处理。
- **禁止元内容**：正文中不得包含思考过程、"我认为"、"接下来"等元内容。
- **表格规范**：多行多列数据必须用 `write_table_to_docx` 写入，禁止 Markdown 表格语法。
- **图题规范**：图题必须用 `write_figure_caption_to_docx` 写入。
- **基于素材**：每节内容必须基于 `search_materials` 检索到的素材撰写，不得凭空捏造。
- **分段写入**：正文中用换行符分隔段落，系统自动处理为 Word 独立段落。
- **禁止重复**：根据工具返回的「当前已写至」判断进度，只写尚未写入的下一节。

## 用户总指示

{system_prompt}

## 论文结构模板

{template}

（素材通过 search_materials 按需检索；格式要求通过 read_format_spec 按需读取；章节规范通过 read_chapter_spec 按需读取。不要跳过这些步骤。）"""


def build_agent(
    user: str,
    materials_text: str,
    docx_path: Path,
    existing_docx_text: str | None = None,
    *,
    streaming: bool = True,
):
    """构建论文生成 LangChain Agent（基于 langgraph）。

    流程：
    1. 将素材构建/加载为 RAG 向量库
    2. 创建共享状态与 LangChain 工具
    3. 使用 langgraph 的 create_react_agent 组装 Agent
    """
    print("[Agent] 构建/加载 RAG 向量库...")
    vectorstore = get_or_build_vectorstore(materials_text, user)

    ctx = ThesisContext(
        docx_path=docx_path,
        existing_docx_text=existing_docx_text,
        vectorstore=vectorstore,
    )
    tools = create_thesis_tools(ctx)

    llm = get_llm(streaming=streaming)
    system_message = _build_system_message()

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=system_message,
    )
    return agent
