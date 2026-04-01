---
name: format-rules
description: 当任务涉及字体字号、段落排版、页面设置、图表格式时使用本技能。先读索引，再按需读取规则文件。
---

# format-rules

## Instructions

1. 先 `read_file`：`/config/智科/skills/format-rules/files/论文要求-索引.md`（虚拟路径；`/` 为项目根）。
2. 按需读取同目录下：
   - `论文要求-页面设置.md`
   - `论文要求-字体与字号.md`
   - `论文要求-段落与排版.md`
   - `论文要求-其他要求.md`
   完整虚拟路径示例：`/config/智科/skills/format-rules/files/论文要求-页面设置.md`
3. 写入正文、表格、图题前核对规则，再调用对应写入工具。
