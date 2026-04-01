---
name: plan-progress
description: 当任务涉及续写、补写、避免重复、修复错序时使用本技能。依据 template/chapters/progress 先规划再写入。
---

# plan-progress

## Overview

本技能约束“先计划、后写入”，并用 progress 文件避免重复与跳写。

## Instructions

1. 先读取计划输出（PlanAgent 的 next target / missing_titles）。
2. 只允许写入当前 `NextTarget`，禁止写入更后面的标题。
3. 写入前检查：
   - 当前标题是否与 `NextTarget` 完全一致；
   - 写入工具是否匹配内容类型（正文/表格/图题）；
   - 是否会重复写入同编号槽位。
4. 若发现 progress 与模板顺序冲突，先执行修复（截断错序部分）再继续。
5. 每轮写入后重新读取 progress，更新下一轮计划。
