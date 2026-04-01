---
name: format-rules
description: 当任务涉及字体字号、段落排版、页面设置、图表格式、关键词数量时使用本技能。先读索引，再按需读取对应规则文件。
---

# format-rules

## Overview

论文格式按需读取，避免一次性把全部规则塞进上下文。

## Instructions

1. 先 `read_file` 索引：`/config/软件学院/skills/format-rules/files/论文要求-索引.md`（虚拟路径；`/` 为项目根）。
2. 再按需读取：
   - `/config/软件学院/skills/format-rules/files/论文要求-页面设置.md`
   - `/config/软件学院/skills/format-rules/files/论文要求-字体与字号.md`
   - `/config/软件学院/skills/format-rules/files/论文要求-段落与排版.md`
   - `/config/软件学院/skills/format-rules/files/论文要求-其他要求.md`
3. 将规则映射到写入动作：正文/标题 → `write_section_to_docx`；表格 → `write_table_to_docx`；图题 → `write_figure_caption_to_docx`。
4. 规则冲突时，优先「当前章节规范 + 索引中更具体条目」。
