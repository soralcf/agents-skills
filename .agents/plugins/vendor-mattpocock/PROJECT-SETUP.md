# 项目接入：保持 Matt 技能原样

[返回阶段索引](README.md)

本组不包含 ask-matt 或 setup-matt-pocock-skills。上游技能要求的项目配置仍需提供；本仓库只提供技能文件，不会自动创建项目文件、远端标签或 issue。

## 先选择任务载体

- 本地 Markdown：适合先在单仓库建立流程，无需远端服务。
- GitHub、GitLab 或其他 tracker：在项目配置中记录仓库/项目标识、读取与更新方法、权限和依赖关系表达方式。

使用项目已有规则，避免同时维护本地和远端两份互相矛盾的任务状态。

## 提供上游期望的三个文件

在需要这些流程的项目内提供下列文件，并从项目的 AGENTS.md 引用，让后续会话知道何时读取它们：

1. `docs/agents/issue-tracker.md`：任务位置、编号解析、查询/读取/发布/更新方式、阻塞关系、子任务、认领与 wayfinding 操作。
2. `docs/agents/triage-labels.md`：类别 bug/enhancement；状态 needs-triage/needs-info/ready-for-agent/ready-for-human/wontfix 到项目实际标签的映射。每个任务恰有一个类别和一个状态。
3. `docs/agents/domain.md`：领域术语表及 ADR 的位置与读取规则。使用现有布局；常见布局是根目录 CONTEXT.md 与 docs/adr/。

可从 [本地 tracker 模板](templates/issue-tracker-local.md) 起步。这份模板只定义存储接口，不修改任何 skill。若启用外部 PR 分诊，另行明确作者范围、PR/issue 编号解析以及 PR 验证步骤；模板默认不启用。

可将 [项目配置示例](templates/skill-project.json) 复制为项目根目录的 `.skill-project.json`，按项目填写路径和检查命令。然后从本仓库运行只读检查：

```bash
python3 .agents/skills/skill-maintainer/scripts/skill_manager.py doctor \
  --project /absolute/project/path --workflow matt-delivery --spec path/to/spec.md
```

也可以用 `--skill implement` 只检查一个入口。doctor 会展开调用依赖，只检查本地文件是否存在且非空，不执行命令、不连接 tracker，也不判断内容是否正确。缺失项退出码为 1；仅有提示时退出码为 0。

## 使用前要明确的行为

- to-spec/to-tickets 会向配置的载体发布；triage 会更新状态，部分结果会关闭任务。用户调用时应明确操作对象和范围。
- code-review 使用 Git 比较基线、项目规范和规格来源。没有规格时只能报告该维度缺失；不能凭空补出需求。
- implement 原文包含提交当前分支，项目应明确检查命令和提交范围。
- teach 使用可写学习目录，具体产物以原始 SKILL.md 及其配套格式为准。
- writing-for-agents 的平台专属技能元数据建议保持上游原文；编写新技能时应以当前客户端的技能配置说明为准。

## 来源与适配

UPSTREAM.lock.json 固定提交、原始目录哈希、打包树哈希与排除路径。除声明排除的 agents/openai.yaml 外，上游选中目录内的全部文件必须匹配源提交。打包不扩大执行授权，也不替换项目配置。
