# 论文 AI 编写（LangChain + RAG）

流程：从 `data/input/{user}` 读取素材 → 提取/同步到 `data/extracted/{user}` → 构建向量库（`data/vectorstore/{user}`）→ LangChain Agent 按模板逐章写入 `output/{user}.docx`（默认终端流式输出进度）。

## 运行方法

1. 放入素材
   - 将多份 `.docx` / `.md` / `.sql` 放入 `data/input/{user}/`
2. 执行
   ```bash
   uv run main.py
   ```
   会进入交互式选择模板包（`--profile`）和学生（`--user`），然后生成 `output/{user}.docx`。

可用参数：
- `uv run main.py --list-profiles`：列出 `config/` 下可用模板包
- `uv run main.py --profile 软件学院 --user 张三`：直接指定模板包和学生
- `uv run main.py --no-stream`：关闭终端流式输出（整段输出更适合写日志）

## 输出与缓存

- 第一步（可跳过）：`data/extracted/{user}` 下已存在素材则跳过提取
- 第二步（RAG 缓存）：向量库保存在 `data/vectorstore/{user}`
- 论文输出：`output/{user}.docx`
- 断点续写进度：`output/{user}.progress.txt`

## 模型配置

模型地址/模型名在 `core/llm.py` 中配置，API Key 优先读取环境变量 `DEEPSEEK_KEY`（DeepSeek 等 OpenAI 兼容接口）。
