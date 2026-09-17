---
status: draft
type: design
module: project-context
last_updated: 2026-09-16
---

# project-context：S0–S2 实现契约

依据：工作区已确认设计 `docs/archive/raw/discussions/project-context/2026-09-16-project-context-skill-design.md`。用户已要求用 skill-build 实现。完整档，不重复需求访谈。

## S0 与 S1

跨项目重复使用、文件收集与增量有确定性脚本、外部来源需要状态与授权治理，因此建立独立 Skill。已确认：完整底稿不按议题裁剪；可超长；手动更新；外部飞书/Issue/PR/部署与生产资料纳入；AI 会话排除；生产数据首次具体配置、以后按范围只读采集；默认本地导出、上传独立授权。

仓库存在用户修改的 skill-build 模板以及未跟踪的其他 Skill/文档，本次不覆盖、不提交。新 Skill 名 `project-context`。使用独立 Git 分支，新增文件局限于 skills/project-context 和本目录。

工具盘点：本会话有文件/进程工具，没有飞书/GitHub/通用生产数据库 MCP；本机有 gh 与 lark-cli。不能用「不存在的连接器」作为完成依据。Skill 通过可核验的 CLI 或宿主已有只读工具取数，接入统一快照契约；连接器与项目账号能力在具体项目执行时核验。不会在实现通用 Skill 时连接用户生产系统。

| 工具/接口 | 使用字段 | 不使用/边界 | 失败 |
|---|---|---|---|
| 文件与 Git | project root、文件字节、stat、status、HEAD | 不根据 gitignore 静默剔除本地资料，不读取聊天数据库 | 缺口/部分完成 |
| gh api | --method GET、endpoint、--paginate、--slurp、--hostname | 不 POST/PATCH，不拿前 N 个 Issue 当全部；正文保留为 JSON | 非零退出保留旧快照 |
| lark-cli | schema、wiki 节点枚举、docs +fetch --scope full --detail full --doc-format xml | 不只读 outline/keyword；媒体附件需另取；读取匹配内置 skill | 权限、缺页、媒体失败均显式标记 |
| 生产宿主工具 | 具体配置的环境、字段、窗口、只读机制、预算 | 不执行任意远程命令、不把 SQL 前缀当只读证明、不自动扩大权限 | 标未采集/部分结果，不伪造全量 |
| 快照导入 | 下述 envelope、完整原文与附件 | 不是模型凭空声明已经取数 | 拒绝错 run/scope 与不合法数据 |

## S2 定位与流程

像认真交接项目的维护者：源材料全文与详细解释互相对应，疑点可追溯，不追求摘要短小。外部生产工具因项目而异，采用显式来源配置与稳定快照边界，而不建立万能连接器框架。

默认每项目 `.project-context/` 本地状态，不改原业务文件或 gitignore；目录内保存配置、原文对象、运行清单、说明与导出。脚本用 Python 标准库，不要求模型 API。

CLI（共同契约，新增子项保持兼容）：

```
context.py init --project PATH [--state PATH] [--name NAME]
context.py scan --state PATH
context.py ingest --state PATH --input ENVELOPE.json
context.py note --state PATH --input NOTES.json
context.py build --state PATH [--brief FILE] [--max-part-chars N]
context.py status --state PATH
```

init 生成 config.json。scan 创建新运行，盘点所有范围内文件、保留旧外部材料但将其标为尚未刷新、检测变化。ingest 接收本轮来源快照。note 接收模型根据材料实际写出的详细说明及材料指纹关联。build 确定性组装全文与覆盖状态；材料或说明不全时生成 partial，不更新 latest-complete。不带 brief 时不继承旧议题。大文件不截断；不支持的二进制交付附件并标待解释；分卷不得丢字节。已有快照、说明可按指纹复用，失败后保留上次完整版本。

config 的 sources 为数组，每项至少 {id, kind, label, scope}；来源 id 唯一，scope 为稳定对象。production 源还含 approval、window、fields、budget 和 read_only 约定。采集器不存凭证明文，读取已有账号或环境引用。未经配置授权不调用生产工具。

外部快照 envelope：schema_version=1，source_id，run_id（scan 当前输出），scope_hash（scan 中该源的配置指纹），status=complete/partial/unavailable，mode=full/delta，enumeration_complete，permissions_verified，collected_at，coverage，items，deleted_ids，errors。items 每项包含 id、title、locator、version/updated_at，以及 content（全文字符串）或 content_file（相对 envelope 的文件）；可附 attachments[{path,name}]。原文与附件经过预定脱敏处理；凭证不落入版本缓存。部分结果不可使未出现的旧对象被删除；full+完整枚举+权限已核验才可对账删除，delta 仅接受明确 deleted_ids。

notes 格式由 core script 输出说明，基本结构为 schema_version、sections 数组；section 包含 id/title/content 与 covers 映射（材料键到当前内容指纹）。变化、删除或新增材料会使相关说明或全局覆盖检查失效。解释写作与收录完成分开报告。

## 输出与考点

七部分：导读版本、产品全貌、技术模块、当前状态演化、运行证据、原始资料全文、覆盖冲突变更。测试分别验证完整原文、跨模块解释依据、时间/环境、实际工作区状态、来源失败不误删除、不因 brief 缩减、完整版本保留、附件和脱敏。

正例：建立完整项目底稿；更新本地与飞书/Issue/生产快照；新功能议题附加；中断后继续；不带旧议题导出。近似负例：解释单个函数；总结 AI 会话；review 并部署 PR；单篇飞书下载；仅讨论新增功能。详细评测集单独保存。

资源分层：SKILL.md 负责流程；references 负责来源与原文完整性/解释；scripts 负责采集与状态、验证/组装；assets 负责来源配置与说明模板。具体写作资源由文档 agent 创建，与本 CLI 对齐。

## 完备性核对

6项满足本次通用能力设计：有≥3近似负例、明确不处理实现/发布/会话；七部分对应验收考点；已核对本机 CLI 参数并定义确定性导入字段；≥5具体输入样本；失败/缺权限/大文件/中断的处理明确。实际生产源配置留在首次项目接入，不能虚构可用账号或 API。

S3 开始撰写。S4 分开报告确定性回归、模型触发、with/without 行为对照、人工抽检。未实际执行的部分标明；不以脚本通过代替模型质量评测。
