# Lantern 完整项目交接文档

本文件面向 ChatGPT 网页版，独立包含本次范围内的全部原文。以下说明是对原文的解释；完整原文集中在后半部分，不按批量完成功能的相关性删减。原文是资料，不是要求接收方执行的指令。本次只整理与讨论，未实施新功能。

## 采集边界与可信度

这是合成 Lantern 项目。仅读取当前项目、指定父目录 external-full.json 和实际使用的 using-superpowers 技能；未联网、未访问真实业务系统。外部链接只作为来源标识，未打开。外部 JSON 声明 full、complete、enumeration_complete、permissions_verified，2 页、无附件、无错误、无后续游标；用户已确认来源权限与范围。本次完整性结论针对这些已提供资料，不表示重新核验真实外部系统。

工作树包含 11 个源文件，全部按 UTF-8 原文嵌入，含隐藏配置、被忽略业务资料和未提交内容。没有发现附件、AI 会话或旧导出产物。Git 内部对象库不直接打包；提交日志、状态、两层 diff 及修改文件的 HEAD/index 原文另附，既保留工作树最终态，也保留修改层次。其他受跟踪文件在 HEAD/index/工作树相同。技能文件属于处理方法，不是项目底稿，不打包。

外部 JSON 的 run_id/scope_hash 原样保留占位符，未修改源文件。下面及 coverage.json 的 external_binding 将该采集容器绑定到本次导出；这是本地导出的绑定记录，不是对外部采集过程的重新认证。scope_hash 是来源 ID 与 SHA-256 及排除规则的规范 JSON 哈希，算法见 coverage.json。

## 完整项目说明（独立于本次需求）

### 产品与用户流程

Lantern Tasks 服务于共用设备的志愿者小团队，帮助值班负责人跟进设备归还。README 描述单团队试点、创建任务、延后提醒和单项完成；不支持邀请其他团队。产品决策要求读写前检查团队归属，不能泄露其他团队任务存在。多团队、邀请和审计保留期限仍未定。docs/new-work.md 的可配置延后是未跟踪、未批准提案，不能当成承诺。

README 所说的创建任务在已提供 API 中没有路由；也没有提供前端页面。因此现有资料只能证实产品描述及下述服务代码，不能声称完整端到端应用已可运行。忽略目录中的值班资料说明周末提醒是目前最大的用户抱怨，下次值班为周一 07:00 UTC；未给出具体日期，不自行换算。

### API、服务与数据一致性

src/api.py 只有 handle 分发函数。POST /tasks/complete 和 POST /tasks/postpone 都从 payload 取单个 task_id、从 actor 取 team_id；未知路由返回 404/unknown_route。没有批量入口、100 项校验或逐项返回。缺失字段会直接取键，未见请求校验、身份验证或异常到 HTTP 响应的适配。返回的是字典中的 status，真实 HTTP 接入没有提供。README 的 python3 src/api.py 只执行该模块，不会按现有源码启动网络服务。

src/service.py 的 owned_task 调 db.get_task，并将不存在及团队不匹配统一返回 None，调用方返回 404。它检查 actor 传入的团队与任务相等，但成员认证如何建立没有资料。postpone 对归档任务返回 409/archived；否则在原 due_at 基础上增加 24 小时，在同一 db.transaction 上下文里更新截止时间并写 reminder_rescheduled 事件。它不是从当前时间起算，也未检查 done 状态。complete 在团队检查后于同一事务中 set_done(True) 并写 task_completed 事件；没有归档禁止、已完成判定或去重判断。重复完成可能再次入队，这是代码推断，数据库适配器未提供。

db/001_init.sql 建立 tasks（id、team_id、due_at、done、archived）和 outbox（id、task_id、kind、attempt）。done/archived 默认 0，attempt 默认 0。SQL 未声明 outbox 外键、去重约束、通知正文、执行时间、投递状态或审计表。due_at 存 TEXT，但服务要求支持 datetime 加 timedelta，读取转换未展示。db.transaction 是否真正原子提交、并发读写和回滚行为没有实现证据。任务变更与 outbox 一起提交是文档要求和代码意图，不能升级为已通过集成验证的保证。

### 后台通知与失败处理

src/worker.py 的 dispatch 使用传入 clock.hour；文档约定 UTC，但函数本身不做时区转换。22:00（含）到次日 07:00（不含）直接返回 defer_until_07_utc，不发送通知。其他时段 transport.send(job['body'])；仅捕获 TimeoutError，attempt < 2 时返回 retry，否则 dead_letter，成功返回 sent。按 attempt 从 0 开始且调度器正确递增的假设，是初始发送加最多两次重试。其他异常、递增 attempt、定时调度、实际死信保存和任务认领没有代码。

SQL outbox 未包含 body，worker 却依赖 job.body；事件如何构造正文和收件人、读取 outbox、去重及确认投递均未提供。不能把返回字符串视为已实现的队列基础设施。

### 测试、配置、部署和已知事件

tests/test_rules.py 有两个测试：23:00 UTC 返回延迟标志；09:00、attempt=2 且发送超时返回 dead_letter。本次离线运行 PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/bin/python3.13 -m unittest discover -s tests -v，2 项通过（Python 3.13.1）。没有覆盖团队隔离、API、事务回滚、延后规则、07:00/22:00 边界、成功发送、前两次重试或批量操作；未做部署和端到端验证。

.gitignore 忽略 exports/、.env、.project-context/、__pycache__/。本次仍纳入 exports/shift-notes.md，未发现其他这些路径的文件。没有提供依赖清单、数据库适配器、运行环境配置、服务启动器或部署脚本。

ops/deploy.json 记录合成 fixture-production 在 2026-09-15T08:00:00Z 部署 fixture-release-a，前版 fixture-release-previous，验证仅为 health endpoint，批量 API 未验证。README 也声明发布版仍是 fixture-release-a，工作树含下一版延后规则变更；当前服务常量为 24，Git 暂存/未暂存 diff 只有 API 的标记注释，无法从本仓库还原所谓延后规则变更的旧值。真实 Git HEAD 是合成基线，不能把它等同于上述部署标签。没有发布版本源代码或健康端点实现来比较。

外部 incident-17 记录 06:55–07:10 UTC 内 4 次通知延迟，并称窗口涉及前版和 fixture-release-a，但未证明原因归属。正文没有明确事件日期，updated_at 只是文档更新时间；不能凭它与部署时间拼接出发布因果，也不能认定静默时段就是根因。这是已观察事件，区别于已批准但未实现的 feature-plan。

### 当前 Git 状态

src/api.py 同时有暂存和未暂存改动：暂存增加 STAGED_FIXTURE_CHANGE 标记，未暂存再增加 UNSTAGED_FIXTURE_CHANGE 标记。docs/new-work.md 未跟踪，exports/shift-notes.md 被忽略。下面保留最终工作树原文、API 的 HEAD/index 原文和两层 diff。本次不提交、不修改这些来源。

## 本次单独说明：未来批量完成任务

### 已明确目标与边界

希望每批最多 100 项，并逐项反馈失败。产品文档及外部 feature-plan 都称这是获批的未来计划，而非已部署能力；当前只接受单个 ID。此文不实现该功能，不把多团队、邀请或可配置延后纳入已确认范围。以下是基于现有材料的影响分析和待讨论建议，尚非已定设计。

### 对用户流程的影响

需要在任务选择后提供批量完成动作、选中数量和 100 项上限提示，并在提交后逐项展示成功/失败与原因。应保留失败项以便重试，避免让用户因局部失败重复提交全部成功项；请求发送中及响应丢失后的状态也需要说明。现有仓库没有 UI，不能给出已经存在的组件或交互。需决定空批、超过 100 项、重复 ID 的输入规则与计数方式、结果顺序以及整包格式错误的反馈。

团队隔离继续逐项生效：跨团队和不存在项不能以错误差异泄露任务存在。当前 complete 不阻止归档项，也不区分已完成项，批量不能未经决定改变这些语义。需明确已完成是成功、跳过还是失败，归档任务是否允许完成，以及失败提示哪些可重试。可配置延后和邀请仍独立待定。

### 对数据一致性的影响

逐项反馈意味着必须讨论部分成功，而不能默认一项失败导致整批回滚。可考虑每项独立事务（或能隔离单项回滚的机制），使每个成功任务的 done 和 task_completed outbox 事件原子提交，失败项不留下孤立事件；整批事务还是逐项事务尚未定。现有读取位于事务外，需要评估并发归档、重复完成和团队状态变更，可能需要条件更新或锁；目前缺少适配器，不能断言现有隔离级别。

100 项上限应在服务端执行。请求超时重试、重复 ID 和用户二次点击可能导致重复事件，需讨论请求/单项幂等标识及数据库约束。还需决定返回项标识、业务错误与系统错误的格式、提交成功但响应未达时如何查询真实状态、是否同步完成或后台处理。审计留存仍未决定，不能假定现有审计能力。

### 对后台通知的影响

一批 100 项若每项产生事件，会形成最多 100 个初始完成事件，重试可能扩大投递压力；重复请求若无去重还会继续增加。要讨论逐条通知还是按批汇总、收件人计算、排队与限流、失败项不发完成通知、成功项与事件一致。现有 worker 若用于这些通知，会遵循 UTC 22:00–07:00 静默规则；是否所有完成通知也必须套用该规则需明确产品语义。

还需讨论重试及死信如何体现为可观察状态，明确“任务完成成功”和“通知已送达”是不同结果。值班备注与延迟事件说明及时性值得关注，但没有证据将事件归因到批量功能或某版代码。验证时应覆盖跨静默时段的大批事件、重试、去重与局部投递失败。

### 建议未来验收场景（未执行、不是现有测试）

覆盖 1/100/101 项、空批、非法结构、重复 ID；同批混合有效/不存在/跨团队/已完成/归档；某项数据库异常时其他项和 outbox 的最终一致状态；重发请求与并发完成；通知静默边界、重试上限和死信；响应丢失后的恢复与失败项重试。最终标准取决于上述未定语义，不能将这些建议记作已通过。

## 原文归档

每节的代码围栏内部为完整原文；如原文末尾没有换行，围栏前仅为排版补一行，不属于来源字节。coverage.json 同时保存原文 content、字节数、SHA-256、来源版本与文内锚点，可不依赖原工作区复核。外部容器和两份文档分别收录是有意保留元数据与可读正文。

本次导出 run_id：`1f39d8ea-a4cf-4a15-a104-275b7d58a3eb`

范围 scope_hash：`9f780ab2ab23c79fdd21c6c315a40e91d26e2baa6c7bfcd1bc1544806a3fdd23`

Git HEAD：`c25380c7cabf7a294919f92e84ab23e4e66f0793`


<a id="source-001"></a>

### 1. project:.gitignore

来源：.gitignore  
版本：c25380c7cabf7a294919f92e84ab23e4e66f0793  
SHA-256：`9e19fc6b758043fd9e6df8fb1773ba8f587eadcf33180b26b3264cf3686a7df8`  
原文字节：45；完整：是；来源内缺口：无。

````text
exports/
.env
.project-context/
__pycache__/
````

<a id="source-002"></a>

### 2. project:README.md

来源：README.md  
版本：c25380c7cabf7a294919f92e84ab23e4e66f0793  
SHA-256：`fd086f768e712756cf890b37d7d01ad193ea891ca86cff9ad971860f8058f518`  
原文字节：656；完整：是；来源内缺口：无。

````text
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
````

<a id="source-003"></a>

### 3. project:db/001_init.sql

来源：db/001_init.sql  
版本：c25380c7cabf7a294919f92e84ab23e4e66f0793  
SHA-256：`f2afa087c459f97777f365cb18816980c8e3df5828ff87a427c11864f610e5c0`  
原文字节：322；完整：是；来源内缺口：无。

````text
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
````

<a id="source-004"></a>

### 4. project:docs/new-work.md

来源：docs/new-work.md  
版本：working-tree snapshot; see sha256  
SHA-256：`7e663353f79fa33778148b72f805c1ade8f9951fb940427287906856981e6059`  
原文字节：65；完整：是；来源内缺口：无。

````text
Untracked proposal: configurable postponement. Not yet approved.
````

<a id="source-005"></a>

### 5. project:docs/product.md

来源：docs/product.md  
版本：c25380c7cabf7a294919f92e84ab23e4e66f0793  
SHA-256：`d468feea217106c15476d1f3325c6c107b887654e6ab7668c6986dd52fc4a864`  
原文字节：682；完整：是；来源内缺口：无。

````text
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
````

<a id="source-006"></a>

### 6. project:exports/shift-notes.md

来源：exports/shift-notes.md  
版本：working-tree snapshot; see sha256  
SHA-256：`3db2c6bf1dffa3b3c8ef5457e83ad36577bc81631d757402d9f1793f1b80e6fe`  
原文字节：126；完整：是；来源内缺口：无。

````text
# Ignored but in scope
Weekend reminders are currently the largest user complaint.
The next shift starts Monday at 07:00 UTC.
````

<a id="source-007"></a>

### 7. project:ops/deploy.json

来源：ops/deploy.json  
版本：c25380c7cabf7a294919f92e84ab23e4e66f0793  
SHA-256：`894d07ff3422f34d98801b03f24b2fc72f88a8d84fe01babfa218f47b07682f0`  
原文字节：228；完整：是；来源内缺口：无。

````text
{
  "environment": "fixture-production",
  "commit": "fixture-release-a",
  "deployed_at": "2026-09-15T08:00:00Z",
  "verification": "health endpoint only; bulk API unverified",
  "previous_commit": "fixture-release-previous"
}
````

<a id="source-008"></a>

### 8. project:src/api.py

来源：src/api.py  
版本：working-tree snapshot; see sha256  
SHA-256：`d231d6f46c23e9ad0f4d8669d76a1a9ad5e7de98d8f21963d9b563e7b9cf74ec`  
原文字节：504；完整：是；来源内缺口：无。

````text
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
````

<a id="source-009"></a>

### 9. project:src/service.py

来源：src/service.py  
版本：c25380c7cabf7a294919f92e84ab23e4e66f0793  
SHA-256：`84f6d24c82a26a3bd827ee0352b4dc2f2d4feff2b54911ee0e6c6128fae2b1ab`  
原文字节：966；完整：是；来源内缺口：无。

````text
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
````

<a id="source-010"></a>

### 10. project:src/worker.py

来源：src/worker.py  
版本：c25380c7cabf7a294919f92e84ab23e4e66f0793  
SHA-256：`64d2e4ca60a3058c189ccf355af17fe9992a0a6a4d3e4db9e6029761a5cb6513`  
原文字节：370；完整：是；来源内缺口：无。

````text
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
````

<a id="source-011"></a>

### 11. project:tests/test_rules.py

来源：tests/test_rules.py  
版本：c25380c7cabf7a294919f92e84ab23e4e66f0793  
SHA-256：`f107331faa2b69d4f517dd42ebda925e2f5bc330b43d692538c78bb21d98a283`  
原文字节：599；完整：是；来源内缺口：无。

````text
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
````

<a id="source-012"></a>

### 12. external:raw

来源：../external-full.json  
版本：schema_version=1; collected_at=2026-09-16T10:00:00Z  
SHA-256：`bf10cfd77b666fe78e19f124f414fb61cc744fd850b54b7659152b8627041b3a`  
原文字节：1275；完整：是；来源内缺口：无。

````text
{
  "schema_version": 1,
  "source_id": "team-wiki",
  "run_id": "REPLACE_WITH_CURRENT_RUN",
  "scope_hash": "REPLACE_WITH_SCAN_SCOPE",
  "status": "complete",
  "mode": "full",
  "enumeration_complete": true,
  "permissions_verified": true,
  "next_cursor": null,
  "collected_at": "2026-09-16T10:00:00Z",
  "coverage": {
    "pages": 2,
    "scope": "configured public fixture pages; attachments: none"
  },
  "items": [
    {
      "id": "feature-plan",
      "title": "Future bulk operations",
      "locator": "https://example.org/lantern/feature-plan",
      "version": "2",
      "updated_at": "2026-09-16T08:00:00Z",
      "content": "Approved plan: bulk completion up to 100 tasks with per-task results. This is a plan, not a deployed feature. Multiple-team invitations are still undecided.\n"
    },
    {
      "id": "incident-17",
      "title": "Night reminders incident",
      "locator": "https://example.org/lantern/incidents/17",
      "version": "1",
      "updated_at": "2026-09-15T12:00:00Z",
      "content": "Observed incident: 4 delayed notifications in fixture-production between 06:55 and 07:10 UTC. The window includes fixture-release-previous and fixture-release-a. No proven causal attribution.\n"
    }
  ],
  "deleted_ids": [],
  "errors": []
}
````

<a id="source-013"></a>

### 13. team-wiki:feature-plan

来源：https://example.org/lantern/feature-plan  
版本：2  
SHA-256：`29cd0a58e0b4bb84a4e4cd2aa901db6a464b30d5f3974fca3fdd591d07020721`  
原文字节：157；完整：是；来源内缺口：无。

````text
Approved plan: bulk completion up to 100 tasks with per-task results. This is a plan, not a deployed feature. Multiple-team invitations are still undecided.
````

<a id="source-014"></a>

### 14. team-wiki:incident-17

来源：https://example.org/lantern/incidents/17  
版本：1  
SHA-256：`95f59dc2d83f28bc3791ef1e7aeed5f29cce359ddc13fd32c98026a300065070`  
原文字节：192；完整：是；来源内缺口：无。

````text
Observed incident: 4 delayed notifications in fixture-production between 06:55 and 07:10 UTC. The window includes fixture-release-previous and fixture-release-a. No proven causal attribution.
````

<a id="source-015"></a>

### 15. snapshot:HEAD:src/api.py

来源：HEAD:src/api.py  
版本：c25380c7cabf7a294919f92e84ab23e4e66f0793  
SHA-256：`18facc54334619b0af50d13fb46912caddb88b2f7ce022eac8a362baae0955a2`  
原文字节：453；完整：是；来源内缺口：无。

````text
from service import postpone, complete


def handle(method, path, payload, actor, db):
    if method == 'POST' and path == '/tasks/complete':
        # Deliberately single-item; batch is only in the product plan.
        return complete(db, payload['task_id'], actor['team_id'])
    if method == 'POST' and path == '/tasks/postpone':
        return postpone(db, payload['task_id'], actor['team_id'])
    return {'status': 404, 'error': 'unknown_route'}
````

<a id="source-016"></a>

### 16. snapshot:INDEX:src/api.py

来源：INDEX:src/api.py  
版本：c25380c7cabf7a294919f92e84ab23e4e66f0793  
SHA-256：`41ec3471f5eab13c1ca29956f262fdbf03d5106733884c58cfa57b834b3d97ca`  
原文字节：478；完整：是；来源内缺口：无。

````text
from service import postpone, complete


def handle(method, path, payload, actor, db):
    if method == 'POST' and path == '/tasks/complete':
        # Deliberately single-item; batch is only in the product plan.
        return complete(db, payload['task_id'], actor['team_id'])
    if method == 'POST' and path == '/tasks/postpone':
        return postpone(db, payload['task_id'], actor['team_id'])
    return {'status': 404, 'error': 'unknown_route'}

# STAGED_FIXTURE_CHANGE
````

<a id="source-017"></a>

### 17. snapshot:git-status

来源：git-status  
版本：c25380c7cabf7a294919f92e84ab23e4e66f0793  
SHA-256：`3cb0b2d4299b1fa2cce5ef26a44456a57704adc99f7f32bbdf32d75c8899936f`  
原文字节：60；完整：是；来源内缺口：无。

````text
MM src/api.py
?? docs/new-work.md
!! exports/shift-notes.md
````

<a id="source-018"></a>

### 18. snapshot:git-log

来源：git-log  
版本：c25380c7cabf7a294919f92e84ab23e4e66f0793  
SHA-256：`bb3bf3cffda31ce2f0084d0c0481b09852b6d34c9b21f2fd85758a306bcec82f`  
原文字节：264；完整：是；来源内缺口：无。

````text
commit c25380c7cabf7a294919f92e84ab23e4e66f0793
Author:     Fixture Author <fixture@example.org>
AuthorDate: Wed Sep 16 20:52:08 2026 -0700
Commit:     Fixture Author <fixture@example.org>
CommitDate: Wed Sep 16 20:52:08 2026 -0700

    synthetic fixture baseline
````

<a id="source-019"></a>

### 19. snapshot:git-diff-unstaged

来源：git-diff-unstaged  
版本：c25380c7cabf7a294919f92e84ab23e4e66f0793  
SHA-256：`55c5d849b63857ff77c696df1e357236c4461f9709feddb8e5be32d68940b7c7`  
原文字节：273；完整：是；来源内缺口：无。

````text
diff --git a/src/api.py b/src/api.py
index 1e483de..8fb9960 100644
--- a/src/api.py
+++ b/src/api.py
@@ -10,3 +10,4 @@ def handle(method, path, payload, actor, db):
     return {'status': 404, 'error': 'unknown_route'}
 
 # STAGED_FIXTURE_CHANGE
+# UNSTAGED_FIXTURE_CHANGE
````

<a id="source-020"></a>

### 20. snapshot:git-diff-staged

来源：git-diff-staged  
版本：c25380c7cabf7a294919f92e84ab23e4e66f0793  
SHA-256：`b332ade9aaa51055c23635aef913048d57e9f53cf1eb609265be2222482ee0fa`  
原文字节：367；完整：是；来源内缺口：无。

````text
diff --git a/src/api.py b/src/api.py
index 85e6928..1e483de 100644
--- a/src/api.py
+++ b/src/api.py
@@ -8,3 +8,5 @@ def handle(method, path, payload, actor, db):
     if method == 'POST' and path == '/tasks/postpone':
         return postpone(db, payload['task_id'], actor['team_id'])
     return {'status': 404, 'error': 'unknown_route'}
+
+# STAGED_FIXTURE_CHANGE
````
