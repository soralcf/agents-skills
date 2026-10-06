---
name: workflow-guide
description: Map a goal to the personal skill workflows, explain how a skill fits, or audit the catalog for gaps and overlap. Invoke explicitly when you want to inspect or navigate this skill library.
disable-model-invocation: true
---

# Workflow Guide

这是个人 Skill 库的只读入口。先读 [references/catalog.md](references/catalog.md)，
再根据用户的目标选择下面一种模式。不要修改、安装、同步或删除 Skill；需要维护时，
建议用户在本仓库中使用 `skill-maintainer`。

## 导航

把用户当前目标映射到一个最短可行工作流：给出入口 Skill、后续步骤、每一步的
完成条件，以及哪些步骤是可选的。优先复用已有工作流；没有匹配项时明确说明缺口，
不要把临时组合冒充已经维护的工作流。

对 user-invoked Skill，只告诉用户下一步应显式调用哪个 Skill；不要声称已经替用户
调用。model-invoked Skill 可以作为工作流中的复用能力解释。

## 解释

解释指定 Skill 的职责、调用方式、输入、产出、依赖关系及其所在工作流。第三方
Skill 要明确其来源；不要把 vendored 内容描述成原创内容。

## 审计

按以下顺序检查：

1. 工作流引用的 Skill 是否都存在。
2. Skill 声明的依赖是否闭合。
3. 哪些 Skill 没有被任何登记工作流引用。
4. 哪些 Skill 的职责明显重叠，或某个工作流包含没有必要的步骤。
5. 哪些常见目标还没有工作流覆盖。

严格区分三个结论：

- **未引用**：静态注册表中没有任何工作流引用它。
- **职责重叠**：两个 Skill 的触发条件或产出近似，需要人工判断。
- **未使用**：需要真实使用记录或用户反馈；不能从静态目录推断。

审计输出使用 `保留`、`待观察`、`候选移除`、`存在缺口`。给出证据和影响，最终
删减决定留给用户。
