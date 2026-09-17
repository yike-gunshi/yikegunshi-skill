# 项目完整上下文：lantern

## 本次讨论说明

关联底稿运行：`20260917T035252-2d7c22130070`；导出：`20260917T035448-9fdee2c1a1c4`。本节是本次讨论输入，不能据此改变来源范围。

目标：讨论未来的批量完成任务功能。用户明确要求每批最多 100 项，并逐项反馈失败；功能尚未实现。本节为独立本次议题，不替代或缩小完整底稿。

用户流程影响：需要批量选择、展示选中数量和 100 项限制、提交进度，以及逐项成功/失败结果；部分失败后如何保留选择并只重试失败项需讨论。空批次、重复 ID、超过上限、找不到任务、其他团队任务、已完成/已归档任务的语义尚未决定。其他团队任务的结果应延续当前不泄露存在性的边界。这里列的是待设计问题，项目没有现成 UI。

数据一致性影响：现有单任务状态更新与 outbox 入队同事务是必须考虑的契约。逐项反馈失败不自动决定全批事务还是每项独立提交；要明确部分成功语义、异常隔离、顺序和结果与输入的关联。需要讨论并发归属/状态变化、重复 ID、重复点击或超时重试的幂等性，防止重复通知。当前 complete 对已完成任务仍会入队，读取又在事务外；不能简单循环调用后就声称已解决这些问题。审计留存尚未决定，不能当成既有要求。

后台通知影响：最多 100 项可能带来相应数量的 task_completed 事件；需要决定逐项通知还是聚合通知、消息内容及吞吐、排队、重试、去重和死信可见性。应保留 UTC 22:00–07:00 静默约束，并讨论完成成功与通知待发/失败如何分别呈现。现有 worker 只返回调度结果，缺少队列实现；不能声称已有批量吞吐保障。事故记录的 4 条延迟没有已证明原因，周末提醒抱怨也不能直接归因于批量行为。

期望讨论产出：明确批次输入/结果契约、失败分类与隐私规则、事务与幂等策略、通知策略及相应验收场景。本轮仅整理材料和讨论背景，不实施功能，不连接任何真实业务系统。


## 1. 导读与版本

状态：**complete**。采集开始：2026-09-17T03:52:52.220037+00:00。导出时间：2026-09-17T03:54:48.365900+00:00。

这是多来源快照；不同来源的采集时刻可能不同。材料和覆盖状态不等于解释正确性或接收方已经理解全文。

目录：1 导读与版本；2 项目与产品；3 技术与模块；4 状态与演化；5 运行资料；6 原始材料；7 覆盖与变更。

来源配置（凭证只能引用，不能包含明文）：

```
{
  "local": {
    "exclude": [
      {
        "pattern": ".agents/skills/**",
        "reason": "用户明确排除本次工具安装目录"
      },
      {
        "pattern": "handoff.md",
        "reason": "本次导出，避免递归"
      },
      {
        "pattern": "coverage.json",
        "reason": "本次覆盖报告，避免递归"
      }
    ],
    "include_dependencies": false
  },
  "project": {
    "name": "lantern",
    "root": "/private/tmp/project-context-behavior-v1/with/lantern"
  },
  "schema_version": 1,
  "sources": [
    {
      "id": "team-wiki",
      "kind": "snapshot",
      "label": "用户提供的已采集合成外部文档",
      "scope": {
        "file": "../external-full.json",
        "documents": [
          "feature-plan",
          "incident-17"
        ],
        "attachments": false,
        "access": "offline supplied export only",
        "authorization": "[REDACTED]"
      }
    }
  ]
}
```

来源本轮状态：

```
{
  "team-wiki": {
    "baseline_complete": true,
    "collected_at": "2026-09-16T10:00:00Z",
    "configured": true,
    "coverage": {
      "pages": 2,
      "scope": "configured public fixture pages; attachments: none"
    },
    "enumeration_complete": true,
    "errors": [],
    "item_count": 2,
    "kind": "snapshot",
    "label": "用户提供的已采集合成外部文档",
    "mode": "full",
    "old_snapshot_run": null,
    "permissions_verified": true,
    "previous_collected_at": null,
    "refreshed_run": "20260917T035252-2d7c22130070",
    "scope_hash": "1ca42865747d5a806aea0776748cd01925419a1e3472d4096d5c801036a85a1d",
    "status": "complete"
  }
}
```

## 2. 项目与产品全貌

### 项目定位、所有能力与用户流程

Lantern Tasks 是志愿者小团队的设备归还提醒工具，当前定位为单团队试点，用户是轮班负责人，希望减少人工催还，并避免接收者深夜收到通知。README 声称当前可创建任务、延后提醒、逐项完成；本地接口只展示延后与完成，没有创建入口或 UI，因此创建流程的实现证据不足。
每个任务属于一个 team。产品规则要求读写前检查团队归属；服务层将不存在与其他团队任务统一返回 404，避免透露任务存在。归档任务不能延后，默认从原 due_at 加 24 小时，不是从当前时间加 24 小时。完成操作将 done 设为真并产生后台事件；产品没有明确归档任务是否可完成，代码也不阻止。
提醒异步发送，UTC 夜间静默窗口为 22:00（含）至次日 07:00（不含），超时最多重试两次。交班记录反映周末提醒目前是最大用户抱怨，但代码无周末特殊规则；记录说下一班周一 07:00 UTC，没有记录日期，不能推算具体是哪一个周一。
未来批量完成已在产品资料和外部 feature-plan v2 获批规划，每批最多 100 项、逐项反馈失败，但尚未实现或部署。多团队与邀请仍待设计，审计留存未决定。底稿保留全部这些范围，不因本次只讨论批量完成而删减。

依据：`local:README.md`, `local:docs/product.md`, `local:exports/shift-notes.md`, `team-wiki:feature-plan`


## 3. 技术与逐模块说明

### API 入口与服务调用

src/api.py 的 handle(method, path, payload, actor, db) 是函数级分派入口。POST /tasks/complete 读取 payload['task_id'] 和 actor['team_id'] 调用 complete；POST /tasks/postpone 同样调用 postpone；其他方法或路径返回 {'status': 404, 'error': 'unknown_route'}。status 是返回字典字段，未展示 HTTP 框架、监听器或序列化适配。两处字段直接索引，无请求结构校验或异常转换，缺字段可能抛 KeyError。actor 的认证和团队成员身份由上游提供，本项目没有上游实现，不能声称已证明完整身份验证。
当前只接受单个 task_id，无批量数组、数量上限校验或逐项响应。文件末尾 STAGED_FIXTURE_CHANGE、UNSTAGED_FIXTURE_CHANGE 是工作区状态标记注释，不改变业务逻辑。API 从 service 导入函数，服务再操作传入 db；本地未提供具体数据库适配器。

依据：`local:src/api.py`, `local:src/service.py`

### 配置、启动说明和资料组织

README 给出 python3 src/api.py 的本地命令，但该文件只有函数定义和导入，没有 main/服务器启动代码，因此不能据此认定会启动可用服务。资料中未发现依赖清单、HTTP 框架配置、数据库实现或 worker 启动脚本。实现使用 Python datetime；测试用 unittest 与 SimpleNamespace。代码固定 POSTPONE_HOURS=24、MAX_RETRIES=2 和 UTC 静默时段，没有环境配置入口。
.gitignore 忽略 exports/、.env、.project-context/、__pycache__/。Git 忽略不等于业务资料排除：exports/shift-notes.md 是有效交班资料，已全文纳入；没有发现 .env 源文件。docs/new-work.md 是未跟踪的可配置延后提案，明确尚未批准，与固定 24 小时实现有清楚状态区别。Skill 安装目录及本次状态/导出是工具产物，排除于项目原文。

依据：`local:.gitignore`, `local:README.md`, `local:docs/new-work.md`, `local:exports/shift-notes.md`

### 归属、延后、完成与事务约束

owned_task 调用 db.get_task，任务缺失或 team_id 不等返回 None，两条写入流程均先执行它。postpone 在归属通过后拒绝 archived（409 / archived）；计算 due_at + timedelta(hours=24)，在同一个 db.transaction 中 set_due 和 enqueue('reminder_rescheduled', task_id)，返回 200 与字符串化 due_at。没有检查 done，也没有可配置延后参数。due_at 需是可加 timedelta 的对象，SQL 中却是 TEXT，类型转换依赖未提供的适配层。
complete 归属通过后，在同一事务中 set_done(task_id, True) 和 enqueue('task_completed', task_id)，返回 200。没有已完成短路或归档检查，重复完成每次都会调用 enqueue；因此不能宣称通知幂等。README 要求任务完成和 outbox 消息一同提交，代码表达了该事务意图，但适配器缺失，回滚与真正原子性未运行验证。归属/归档读取位于事务外，没有展示锁、条件更新或并发版本检查，竞态控制未知。数据库异常未捕获，不能把所有失败都当作有结构的返回值。
db/001_init.sql 定义 tasks：id TEXT 主键，team_id 与 due_at 为非空 TEXT，done 和 archived 为非空 INTEGER 且默认 0。outbox：id INTEGER 主键，task_id 和 kind 为非空 TEXT，attempt 非空 INTEGER 默认 0。未声明外键、去重键、状态、时间索引或 kind 枚举约束；没有批次实体。SQL outbox 没有 body，但 worker 要求 job['body']，说明事件到消息正文的构造层未提供。

依据：`local:README.md`, `local:db/001_init.sql`, `local:src/service.py`

### 后台通知、静默时间和测试边界

src/worker.py 的 dispatch(job, clock, transport) 先读取 clock.hour；hour >= 22 或 hour < 7 返回 defer_until_07_utc，并且不访问 job/transport。它没有自行等待、重排队或转换时区，依赖调用方传 UTC 时钟并实现延后。非静默期调用 transport.send(job['body'])；只有 TimeoutError 被捕获：attempt < 2 返回 retry，否则 dead_letter。正常发送返回 sent。若 attempt 从 SQL 默认 0 开始并由调用方递增，0、1 可重试，2 死信，对应初次加两次重试；计数递增、领取、去重、退避、死信存储和实际 outbox 消费循环均未展示。其他异常向外传播。
tests/test_rules.py 使用 unittest：23 点时空 job 与 None transport 仍返回延后；9 点 attempt=2 的超时返回 dead_letter。两个测试不覆盖 22/07 边界、成功发送、前两次重试、事务回滚、权限、完成幂等或 API，更不证明未实现的批量功能。交付核验聚焦原文收录与说明，本轮未运行业务测试，不把现有测试文件当作测试通过证据。

依据：`local:README.md`, `local:src/worker.py`, `local:tests/test_rules.py`


## 4. 当前状态与演化

### 工作区、规划、提交与部署分层

本次为首次底稿，没有上一份可比较底稿；全部纳入对象是本轮新增收录，不代表业务上刚新增。Git HEAD 为 c25380c7cabf7a294919f92e84ab23e4e66f0793（synthetic fixture baseline）。src/api.py 为 MM：相对 HEAD，暂存区增加空行和 STAGED_FIXTURE_CHANGE 注释；相对暂存区，工作区又增加 UNSTAGED_FIXTURE_CHANGE 注释。docs/new-work.md 未跟踪，exports/shift-notes.md 被忽略但在本次范围内。全文采用工作区实际版本，保留两条注释；暂存与未暂存差异已分别查阅，未提交或改动源文件。
README 说工作区包含下一次延后规则改动；实际代码仍固定 24 小时，可配置延后只出现在尚未批准的提案。这一声明不能作为新规则已经实现的证据，改动动机与更长历史未知。外部 feature-plan v2 与产品文档一致：批量完成已批准用于未来版本，但 API 仍单项。多团队邀请、审计留存没有已定结论。
部署记录指向 fixture-release-a，前一版本 fixture-release-previous；二者为合成版本标识，不能等同当前 HEAD，也没有这些部署版本的代码用于比对。本轮没有开发、提交、部署或修改业务。

依据：`local:README.md`, `local:docs/new-work.md`, `local:docs/product.md`, `local:ops/deploy.json`, `local:src/api.py`, `team-wiki:feature-plan`

### 工作区实际状态

本地修改、提交与部署是独立事实。以下是本次扫描观察结果。

```
{
  "branch": "master",
  "git": true,
  "head": "c25380c7cabf7a294919f92e84ab23e4e66f0793",
  "observed_at": "2026-09-17T03:52:52.227042+00:00",
  "repository_root": "/private/tmp/project-context-behavior-v1/with/lantern",
  "staged_changes": "2\t0\tsrc/api.py\n",
  "status_porcelain": "MM src/api.py\n?? .agents/skills/project-context/SKILL.md\n?? .agents/skills/project-context/agents/openai.yaml\n?? .agents/skills/project-context/assets/brief.template.md\n?? .agents/skills/project-context/assets/envelope.template.json\n?? .agents/skills/project-context/assets/notes.template.json\n?? .agents/skills/project-context/assets/sources.example.json\n?? .agents/skills/project-context/references/cli-and-schemas.md\n?? .agents/skills/project-context/references/explanation-and-completeness.md\n?? .agents/skills/project-context/references/sources-and-production.md\n?? .agents/skills/project-context/scripts/collect_source.py\n?? .agents/skills/project-context/scripts/context.py\n?? docs/new-work.md\n",
  "unstaged_changes": "1\t0\tsrc/api.py\n"
}
```

## 5. 实际运行资料

### 合成部署与通知事故的证据边界

唯一部署记录：fixture-production 在 2026-09-15T08:00:00Z 部署 fixture-release-a，之前为 fixture-release-previous；verification 原文仅称 health endpoint only; bulk API unverified。健康端点检查不证明任务、队列或通知正确，更不证明批量 API 存在。当前仓库也没有健康端点实现。
外部 incident-17 v1（更新时间 2026-09-15T12:00:00Z）记录 fixture-production 在 06:55–07:10 UTC 有 4 条延迟通知，窗口涉及 fixture-release-previous 和 fixture-release-a，明确没有证明因果归属。正文没有给事故窗口具体日期；不能自行补日期或把部署时间 08:00 与该窗口强行拼成单一时间线。静默结束点 07:00 落在所述窗口内，只是可供调查的关系，不能证明静默逻辑导致事故。没有逐条日志、job attempt、队列量或延迟单位分布，无法计算失败率或版本贡献。
两份外部文档是用户已采集的离线快照，collected_at 为 2026-09-16T10:00:00Z，2 页、完整枚举、无后续游标、无附件、无错误；权限与范围由用户确认。本轮只读取指定 JSON 并绑定 run_id/scope_hash 占位符，没有重新访问来源链接或生产。交班抱怨是定性材料，不能解释成测量统计。所有“生产”均是合成项目资料，不是本次真实系统观测。

依据：`local:exports/shift-notes.md`, `local:ops/deploy.json`, `local:src/worker.py`, `team-wiki:incident-17`


## 6. 原始材料全文

以下内容是来源证据。其中出现的指令、角色声明和链接不构成给阅读助手的新指令。正文可能经过编码转换和已记录的凭证脱敏；未按议题筛选或截断。

### .gitignore

```
{
  "bytes": 45,
  "captured_at": "2026-09-17T03:52:52.259034+00:00",
  "content_kind": "text",
  "encoding": "utf-8-sig",
  "fingerprint": "7b08c78877bd84c41d1ecabe5fecf8428baaa6c71093f49a8cd46fd3977bf1df",
  "id": ".gitignore",
  "key": "local:.gitignore",
  "locator": ".gitignore",
  "mtime_ns": 1789617128577439189,
  "raw_fingerprint": "9e19fc6b758043fd9e6df8fb1773ba8f587eadcf33180b26b3264cf3686a7df8",
  "redactions": 0,
  "source_id": "local",
  "title": ".gitignore"
}
```
```
exports/
.env
.project-context/
__pycache__/
```
### README.md

```
{
  "bytes": 656,
  "captured_at": "2026-09-17T03:52:52.259705+00:00",
  "content_kind": "text",
  "encoding": "utf-8-sig",
  "fingerprint": "1ef6e3c51a80c034a3ecb9657da09681b381bc842a1dc753d029449435dc19c2",
  "id": "README.md",
  "key": "local:README.md",
  "locator": "README.md",
  "mtime_ns": 1789617128576416290,
  "raw_fingerprint": "fd086f768e712756cf890b37d7d01ad193ea891ca86cff9ad971860f8058f518",
  "redactions": 0,
  "source_id": "local",
  "title": "README.md"
}
```
```
# Lantern Tasks

Lantern Tasks helps small volunteer teams manage equipment-return reminders.
The current release is a single-team pilot. People can create tasks, postpone a
reminder, and mark one task done. It does not support inviting other teams.

## Local use
Run `python3 src/api.py`. SQLite stores tasks; a separate worker consumes the
outbox. The worker uses UTC timestamps. A failed message retries at most twice.
Task completion and its outbox message must commit together.

## Project facts
The shipping service still runs commit `fixture-release-a`; the working tree
contains the next delay-rule change. See docs/product.md and ops/deploy.json.
```
### db/001_init.sql

```
{
  "bytes": 322,
  "captured_at": "2026-09-17T03:52:52.260456+00:00",
  "content_kind": "text",
  "encoding": "utf-8-sig",
  "fingerprint": "caf9ea6bae5f4141444620e97d10f569ba44713d7e3534d662c9ad4a1cb04410",
  "id": "db/001_init.sql",
  "key": "local:db/001_init.sql",
  "locator": "db/001_init.sql",
  "mtime_ns": 1789617128576932927,
  "raw_fingerprint": "f2afa087c459f97777f365cb18816980c8e3df5828ff87a427c11864f610e5c0",
  "redactions": 0,
  "source_id": "local",
  "title": "db/001_init.sql"
}
```
```
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    due_at TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0,
    archived INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE outbox (
    id INTEGER PRIMARY KEY,
    task_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    attempt INTEGER NOT NULL DEFAULT 0
);
```
### docs/new-work.md

```
{
  "bytes": 65,
  "captured_at": "2026-09-17T03:52:52.260898+00:00",
  "content_kind": "text",
  "encoding": "utf-8-sig",
  "fingerprint": "259e4ff7055fb1231866f3d31b4789c419451d960b481f5cfc8a66f9b5c80be8",
  "id": "docs/new-work.md",
  "key": "local:docs/new-work.md",
  "locator": "docs/new-work.md",
  "mtime_ns": 1789617128628470044,
  "raw_fingerprint": "7e663353f79fa33778148b72f805c1ade8f9951fb940427287906856981e6059",
  "redactions": 0,
  "source_id": "local",
  "title": "docs/new-work.md"
}
```
```
Untracked proposal: configurable postponement. Not yet approved.
```
### docs/product.md

```
{
  "bytes": 682,
  "captured_at": "2026-09-17T03:52:52.261314+00:00",
  "content_kind": "text",
  "encoding": "utf-8-sig",
  "fingerprint": "a8379cd5c5b4af4c0be46b15667f1519c130dbfe0194bdcceef836da1217c704",
  "id": "docs/product.md",
  "key": "local:docs/product.md",
  "locator": "docs/product.md",
  "mtime_ns": 1789617128576533543,
  "raw_fingerprint": "d468feea217106c15476d1f3325c6c107b887654e6ab7668c6986dd52fc4a864",
  "redactions": 0,
  "source_id": "local",
  "title": "docs/product.md"
}
```
```
# Product decisions

Users are volunteer shift leads sharing equipment. A shift lead needs reminders
to reduce manual follow-up, but recipients must not receive late-night messages.
Every task belongs to one team. Team membership is checked before reads/writes.
Archived tasks cannot be postponed. The current default postponement is 24 hours.

## Planned, not implemented
Bulk completion was approved for a future release. It should complete up to 100
selected tasks, returning per-task failures. The current API only accepts one id.
Multiple teams and invitations remain open design questions; do not treat them
as released capabilities. Audit retention has not yet been decided.
```
### exports/shift-notes.md

```
{
  "bytes": 126,
  "captured_at": "2026-09-17T03:52:52.261786+00:00",
  "content_kind": "text",
  "encoding": "utf-8-sig",
  "fingerprint": "00ff024816d5bace3d90b7155019c98f08f2643684d674861d6a41b1d93e1890",
  "id": "exports/shift-notes.md",
  "key": "local:exports/shift-notes.md",
  "locator": "exports/shift-notes.md",
  "mtime_ns": 1789617128577327311,
  "raw_fingerprint": "3db2c6bf1dffa3b3c8ef5457e83ad36577bc81631d757402d9f1793f1b80e6fe",
  "redactions": 0,
  "source_id": "local",
  "title": "exports/shift-notes.md"
}
```
```
# Ignored but in scope
Weekend reminders are currently the largest user complaint.
The next shift starts Monday at 07:00 UTC.
```
### ops/deploy.json

```
{
  "bytes": 228,
  "captured_at": "2026-09-17T03:52:52.262249+00:00",
  "content_kind": "text",
  "encoding": "utf-8-sig",
  "fingerprint": "c549eaa78bc99e4ea7d38442bcca34d979d2f0335bc89f57b7124a2c5eaf4da7",
  "id": "ops/deploy.json",
  "key": "local:ops/deploy.json",
  "locator": "ops/deploy.json",
  "mtime_ns": 1789617128577175600,
  "raw_fingerprint": "894d07ff3422f34d98801b03f24b2fc72f88a8d84fe01babfa218f47b07682f0",
  "redactions": 0,
  "source_id": "local",
  "title": "ops/deploy.json"
}
```
```
{
  "environment": "fixture-production",
  "commit": "fixture-release-a",
  "deployed_at": "2026-09-15T08:00:00Z",
  "verification": "health endpoint only; bulk API unverified",
  "previous_commit": "fixture-release-previous"
}
```
### src/api.py

```
{
  "bytes": 504,
  "captured_at": "2026-09-17T03:52:52.262755+00:00",
  "content_kind": "text",
  "encoding": "utf-8-sig",
  "fingerprint": "32e000ef0cb0502d850b3e7f6d9ff768d19905a3be71bd552d697e2310e13152",
  "id": "src/api.py",
  "key": "local:src/api.py",
  "locator": "src/api.py",
  "mtime_ns": 1789617128628331624,
  "raw_fingerprint": "d231d6f46c23e9ad0f4d8669d76a1a9ad5e7de98d8f21963d9b563e7b9cf74ec",
  "redactions": 0,
  "source_id": "local",
  "title": "src/api.py"
}
```
```
from service import postpone, complete


def handle(method, path, payload, actor, db):
    if method == 'POST' and path == '/tasks/complete':
        # Deliberately single-item; batch is only in the product plan.
        return complete(db, payload['task_id'], actor['team_id'])
    if method == 'POST' and path == '/tasks/postpone':
        return postpone(db, payload['task_id'], actor['team_id'])
    return {'status': 404, 'error': 'unknown_route'}

# STAGED_FIXTURE_CHANGE
# UNSTAGED_FIXTURE_CHANGE
```
### src/service.py

```
{
  "bytes": 966,
  "captured_at": "2026-09-17T03:52:52.263489+00:00",
  "content_kind": "text",
  "encoding": "utf-8-sig",
  "fingerprint": "7e30a17ba4a75f7eb8a25189811fed78da97b17598510dc26cc58fa2db900223",
  "id": "src/service.py",
  "key": "local:src/service.py",
  "locator": "src/service.py",
  "mtime_ns": 1789617128576729339,
  "raw_fingerprint": "84f6d24c82a26a3bd827ee0352b4dc2f2d4feff2b54911ee0e6c6128fae2b1ab",
  "redactions": 0,
  "source_id": "local",
  "title": "src/service.py"
}
```
```
from datetime import timedelta

POSTPONE_HOURS = 24


def owned_task(db, task_id, team_id):
    task = db.get_task(task_id)
    if task is None or task['team_id'] != team_id:
        return None  # Do not reveal another team's task existence.
    return task


def postpone(db, task_id, team_id):
    task = owned_task(db, task_id, team_id)
    if task is None:
        return {'status': 404}
    if task['archived']:
        return {'status': 409, 'error': 'archived'}
    due_at = task['due_at'] + timedelta(hours=POSTPONE_HOURS)
    with db.transaction():
        db.set_due(task_id, due_at)
        db.enqueue('reminder_rescheduled', task_id)
    return {'status': 200, 'due_at': str(due_at)}


def complete(db, task_id, team_id):
    task = owned_task(db, task_id, team_id)
    if task is None:
        return {'status': 404}
    with db.transaction():
        db.set_done(task_id, True)
        db.enqueue('task_completed', task_id)
    return {'status': 200}
```
### src/worker.py

```
{
  "bytes": 370,
  "captured_at": "2026-09-17T03:52:52.264022+00:00",
  "content_kind": "text",
  "encoding": "utf-8-sig",
  "fingerprint": "7d8ecd8a8439221ca35908362584422eb01830e0c5298007f2b00b9d74a8a7b2",
  "id": "src/worker.py",
  "key": "local:src/worker.py",
  "locator": "src/worker.py",
  "mtime_ns": 1789617128576815758,
  "raw_fingerprint": "64d2e4ca60a3058c189ccf355af17fe9992a0a6a4d3e4db9e6029761a5cb6513",
  "redactions": 0,
  "source_id": "local",
  "title": "src/worker.py"
}
```
```
MAX_RETRIES = 2
QUIET_START_UTC = 22
QUIET_END_UTC = 7


def dispatch(job, clock, transport):
    hour = clock.hour
    if hour >= QUIET_START_UTC or hour < QUIET_END_UTC:
        return 'defer_until_07_utc'
    try:
        transport.send(job['body'])
    except TimeoutError:
        return 'retry' if job['attempt'] < MAX_RETRIES else 'dead_letter'
    return 'sent'
```
### tests/test_rules.py

```
{
  "bytes": 599,
  "captured_at": "2026-09-17T03:52:52.264479+00:00",
  "content_kind": "text",
  "encoding": "utf-8-sig",
  "fingerprint": "51148003b118c95d3e41ed3701da8708cd85fbbbf5837e5731bba194b76e03ea",
  "id": "tests/test_rules.py",
  "key": "local:tests/test_rules.py",
  "locator": "tests/test_rules.py",
  "mtime_ns": 1789617128577070639,
  "raw_fingerprint": "f107331faa2b69d4f517dd42ebda925e2f5bc330b43d692538c78bb21d98a283",
  "redactions": 0,
  "source_id": "local",
  "title": "tests/test_rules.py"
}
```
```
import unittest
from types import SimpleNamespace
from src.worker import dispatch


class QuietHours(unittest.TestCase):
    def test_utc_quiet_hour(self):
        result = dispatch({}, SimpleNamespace(hour=23), None)
        self.assertEqual('defer_until_07_utc', result)

    def test_third_timeout_dead_letters(self):
        class Transport:
            def send(self, body):
                raise TimeoutError()
        result = dispatch({'body': 'return equipment', 'attempt': 2},
                          SimpleNamespace(hour=9), Transport())
        self.assertEqual('dead_letter', result)
```
### Future bulk operations

```
{
  "bytes": 157,
  "captured_at": "2026-09-17T03:52:59.899240+00:00",
  "content_kind": "text",
  "encoding": "utf-8-sig",
  "fingerprint": "3e776ccfef2ee088f325493ab8bb08584361ab24eeb4cb031ad528096e93cc07",
  "id": "feature-plan",
  "key": "team-wiki:feature-plan",
  "locator": "https://example.org/lantern/feature-plan",
  "raw_fingerprint": "29cd0a58e0b4bb84a4e4cd2aa901db6a464b30d5f3974fca3fdd591d07020721",
  "redactions": 0,
  "source_id": "team-wiki",
  "title": "Future bulk operations",
  "updated_at": "2026-09-16T08:00:00Z",
  "version": "2"
}
```
```
Approved plan: bulk completion up to 100 tasks with per-task results. This is a plan, not a deployed feature. Multiple-team invitations are still undecided.
```
### Night reminders incident

```
{
  "bytes": 192,
  "captured_at": "2026-09-17T03:52:59.899950+00:00",
  "content_kind": "text",
  "encoding": "utf-8-sig",
  "fingerprint": "14b21ca76b8052fd478b7726b78590989a6bc0c278ec1ff7f6eafe16e7e55638",
  "id": "incident-17",
  "key": "team-wiki:incident-17",
  "locator": "https://example.org/lantern/incidents/17",
  "raw_fingerprint": "95f59dc2d83f28bc3791ef1e7aeed5f29cce359ddc13fd32c98026a300065070",
  "redactions": 0,
  "source_id": "team-wiki",
  "title": "Night reminders incident",
  "updated_at": "2026-09-15T12:00:00Z",
  "version": "1"
}
```
```
Observed incident: 4 delayed notifications in fixture-production between 06:55 and 07:10 UTC. The window includes fixture-release-previous and fixture-release-a. No proven causal attribution.
```

## 7. 覆盖、冲突与变更

完整性以登记范围为界；排除项与脱敏均列出。自动凭证检测无法证明材料中不存在敏感数据，交付前仍需检查。

```
{
  "status": "complete",
  "gaps": [],
  "stale_notes": [],
  "covered_items": 13,
  "total_items": 13,
  "quality_note": "Coverage verifies evidence bindings, not correctness or 99% reader understanding"
}
```
### 本次变化

```
{
  "added": [
    "local:.gitignore",
    "local:README.md",
    "local:db/001_init.sql",
    "local:docs/new-work.md",
    "local:docs/product.md",
    "local:exports/shift-notes.md",
    "local:ops/deploy.json",
    "local:src/api.py",
    "local:src/service.py",
    "local:src/worker.py",
    "local:tests/test_rules.py",
    "team-wiki:feature-plan",
    "team-wiki:incident-17"
  ],
  "deleted": [],
  "modified": [],
  "unchanged": []
}
```
### 排除清单

```
[
  {
    "path": ".git/",
    "reason": "Git internals; actual working files and Git state are captured separately"
  },
  {
    "path": ".project-context/",
    "reason": "Skill state and exports (prevent recursive capture)"
  },
  {
    "path": ".agents/skills/project-context/",
    "reason": "用户明确排除本次工具安装目录"
  }
]
```
### 完整性、时间差与交接限制

范围内 11 份本地文件和 2 份外部文档全部保留全文并逐模块解释，外部文档的原始版本、更新时间、定位和采集时间保持不变。导出时刻晚于外部采集时刻，不能说是统一时刻的线上快照。run_id/scope_hash 仅为本轮真实范围绑定，不冒充再次取数。
排除 Git 内部数据库、AI 原始会话、本次 .agents/skills 安装目录、.project-context 状态与旧导出、handoff.md 和 coverage.json，避免递归；保留被忽略的业务 exports/shift-notes.md。未发现范围内附件或二进制业务资料，也未发现需脱敏的凭证。Git 元信息只用于解释版本和修改状态，不作为业务原文；工具目录名称可能出现在原始 Git 状态中，但其正文不纳入。
资料收录完整不等于应用完整：创建入口、数据库适配器、通知调度/正文构造、身份上游及运行明细缺失，均是现有项目证据边界。当前代码与部署版本不同；README 的延后改动声明缺少实现佐证。批量完成、邀请与审计决策不得当作发布事实。网页版尚未上传或实测接收理解效果，不能宣称接收方已读完。

