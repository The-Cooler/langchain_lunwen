---
name: chapter-spec
description: 当任务是撰写或续写某一章/节时使用本技能。先通过 read_chapter_spec 取规范，再按「结构+段落要求+字数」输出。
---

# chapter-spec

## Overview

把当前模板包下 `chapters` 中的规范落实为写作步骤。路径以 **虚拟根** 为准（`/` = 项目根），与 `FilesystemBackend(virtual_mode=True)` 一致。

## Instructions

1. **优先**调用工具 `read_chapter_spec(章节标题)` 获取规范全文；**不要**用 `ls` 盲扫目录。
2. 若必须用 `read_file`，章节规范位于：`/config/<当前模板包名>/chapters/<与标题匹配的>.md`；其中 `<当前模板包名>` 与系统提示中的「当前论文配置模板包」一致（本包为 `软件学院`）。
3. 按规范中的 `## 结构`、`## 段落要求`、`## 字数`、`## 细则` 约束输出。
4. 占位词（如「模块1/同上」）须替换为真实名称，不得原样写入正文标题。
5. 不得跨章节提前写后续标题。
