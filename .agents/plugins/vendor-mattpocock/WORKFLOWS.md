# 常用工作路线

[返回阶段索引](README.md) · [项目接入](PROJECT-SETUP.md)

阶段编号帮助找入口。箭头是建议顺序；并列技能是按需分支，不能据此推断所有步骤必须执行。

| 任务 | 入口与常用路线 | 完成标准 |
|---|---|---|
| 持续学习 | teach；缺事实用 research，没听懂用 wait-what | 目标、资源、课程与学习记录形成持续学习工作区 |
| 从想法到交付 | grilling → 按需设计/原型 → to-spec → to-tickets → implement | 规格的验收条件被实现并验证 |
| 大型模糊项目 | wayfinder → research / prototype / grilling + domain-modeling → 规格规划 | 关键决策有记录，下一步路线明确；不等于已实现 |
| 修复 Bug | diagnosing-bugs → tdd → code-review | 故障得到复现，修复通过行为回归验证 |
| 架构改进 | improve-codebase-architecture → 选择候选 → grilling + domain-modeling → 规划实现 | 方案解释具体摩擦、边界与测试收益 |
| 问题分诊 | triage → 验证事实 → 按需澄清 → 更新任务说明与状态 | 事实、未决信息与执行条件清楚 |
| 向他人收集信息 | to-questionnaire | 每个待决问题都有面向正确对象的问项 |
| 审查与集成 | code-review；出现 Git 冲突时用 resolving-merge-conflicts | 规范与规格分别审查，冲突按双方意图解决 |
| 交接 | handoff；必须人工操作时用 wizard | 接手者能找到当前状态、证据与下一步 |
| Agent 文档维护 | writing-for-agents | 触发条件、信息结构和完成标准清楚 |

## 内部调用与跨阶段能力

- grill-me 是 grilling 的显式入口；grill-with-docs 组合 grilling 与 domain-modeling。选一个入口即可。
- implement 原文已要求按需 TDD、执行检查、code-review 和提交当前分支。导航不是要求再重复执行这些步骤。
- wayfinder 的票据解决决策问题；to-tickets 的票据交付可验证行为。两者不应混为一个任务列表。
- domain-modeling 可随澄清和设计持续维护，tdd 在实现期间循环使用，handoff 可随时使用。
- teach 完整保留上游长期教学流程，会创建学习目标、资源、记录、HTML 课程和共享资源；它与 learn-anything 并存。wait-what 原文指定简化技术英语；可以在调用时明确要求中文，技能文件不作翻译。

## 在哪里找到这些技能

每个技能只有一份，位于仓库的 `.agents/skills/<name>/`；构建产物在 `dist/vendor-mattpocock/skills/<name>/`。用技能名或它的触发语调用，避免与另外单独安装的同名技能混淆。阶段编号只用于仓库导航，不保证任何客户端界面按阶段分组。

上游的 Skill tool 与斜杠调用文字保持原样。本插件提供调用依赖清单，运行时仍按客户端自己的技能加载机制读取对应技能。技能文件可被加载，不等于每个完整流程都已端到端执行。

上游树与打包树的摘要逐项记录在 [UPSTREAM.lock.json](UPSTREAM.lock.json)，可用 `skill_manager.py validate` 复核。
