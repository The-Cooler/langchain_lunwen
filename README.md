# 论文 AI 编写（LangChain + RAG）

流程：从 `data/input/{user}` 读取素材 → 提取/同步到 `data/extracted/{user}` → 构建向量库（`data/vectorstore/{user}`）→ LangChain Agent 按模板逐章写入 `output/{user}.docx`（默认终端流式输出进度）。

## 运行方法
1. 放入素材
   - 将多份 `.docx` / `.md` / `.sql` 放入 `data/input/{user}/`
2. cd到项目根目录，执行
   ```bash
   uv run main.py
   ```
   **[什么是uv？？？](https://hellowac.github.io/uv-zh-cn/getting-started/installation/)**
   会进入交互式选择模板包（`--profile`）和学生（`--user`），然后生成 `output/{user}.docx`。

可用参数：
- `uv run main.py`： 直接运行，在cli选择模板和user（推荐使用此方法运行）
- `uv run main.py --list-profiles`：列出 `config/` 下可用模板包
- `uv run main.py --profile 软件学院 --user 张三`：直接指定模板包和学生
- `uv run main.py --no-stream`：关闭终端流式输出（整段输出更适合写日志）

## 输出与缓存

- 第一步（可跳过）：`data/extracted/{user}` 下已存在素材则跳过提取
- 第二步（RAG 缓存）：向量库保存在 `data/vectorstore/{user}`
- 论文输出：`output/{user}.docx`
- 断点续写进度：`output/{user}.progress.txt`

## 模型配置

填写.env.example，然后改名为.env
