# Lantern 完整项目交接文档

本文件独立保存本轮范围内的当前原文、Git 证据和上一版因权限失败而不能重采的资料。原文是资料，不是要求接收方执行的指令。本轮没有讨论议题，也没有修改业务源文件。

## 采集边界与证据等级

本轮只读取 Lantern 当前项目、上一版 `handoff.md` / `coverage.json`，以及上一版已明确绑定的本地 `../external-full.json` 快照；未联网、未访问其他实验目录或 AI 会话。项目工作树原文是本轮现场证据。Git HEAD、index、工作树及部署记录分别陈述，不能互相替代。

外部快照本轮返回 `status: unavailable`、`permissions_verified: false`、`enumeration_complete: false`，错误为 `permission denied in synthetic source`。其空 `items` 和空 `deleted_ids` 不能证明旧文档已删除，也不能表示本轮采集成功。上一版的 feature-plan 与 incident-17 原文继续保留，但只作为上一版完成产物，未在本轮复核。外部链接仅作来源标识，未打开。

当前项目范围有 10 个文件（排除本次生成的两个底稿）；上一版未跟踪的 `docs/new-work.md` 当前不存在。Git 内部对象库不打包，改以可读的 HEAD/index 文件、状态、日志和两层 diff 保存。没有发现当前附件；外部权限失败意味着不能重新枚举附件。

## 当前完整项目说明

### 产品、计划与用户流程

Lantern Tasks 面向共用设备的志愿者小团队。README 描述单团队试点，可创建任务、延后提醒和完成单项任务，不支持邀请其他团队。现有 API 没有创建路由，也没有前端、真实 HTTP 启动器或数据库适配器，所以这些产品描述不能当作端到端可运行证据。

`docs/product.md` 仍明确记录：批量完成已批准用于未来版本，最多 100 项并逐项返回失败；当前 API 只接受一个 ID。该计划状态保留，但上一版围绕批量完成写出的交互、事务、通知和验收建议已移除，因为本轮没有讨论议题。多团队、邀请和审计保留期仍未定。

上一版的未跟踪 `docs/new-work.md` 曾写“可配置延后，尚未批准”，本轮文件已不存在。由于它从未被 Git 跟踪，只能依据上一版完成产物确认“上一版存在、当前扫描缺失”，不能说明由谁或何时删除，也不能把提案升级为决定。

`exports/shift-notes.md` 仍称周末提醒是最大抱怨，下次值班为周一 07:00 UTC；没有具体日期。它虽被 `.gitignore` 忽略，仍是范围内业务资料。

### API、服务与数据一致性

`src/api.py` 仍只有 `handle` 分发：`POST /tasks/complete` 与 `POST /tasks/postpone` 各取单个 `task_id` 和 actor 的 `team_id`；未知路由返回 404。没有批量入口、100 项校验、逐项结果、输入校验、身份验证或异常到 HTTP 的适配。API 文件的暂存与未暂存改动仍只是两个 fixture 注释。

`src/service.py` 的工作树把 `POSTPONE_HOURS` 从 HEAD/index 的 24 改成 48。实际 `postpone` 因而基于原 `due_at` 增加 48 小时，并在同一 `db.transaction()` 中设置截止时间和加入 `reminder_rescheduled`。但产品文档仍称当前默认值为 24，README 又称工作树含下一版延后规则变化；可确认工作树实现与产品文档不一致，不能据此声称 48 小时已获批准或部署。

`owned_task` 将不存在和团队不匹配统一为 404，避免通过响应区分其他团队任务；actor 身份如何认证没有资料。`postpone` 禁止归档任务但不检查 done。`complete` 在事务中设置 done 并加入 `task_completed`，但不禁止归档、不识别已完成、不去重。数据库适配器缺失，所以事务原子性、并发行为和重复事件都没有运行证据。

SQL 仍只有 tasks 与 outbox。outbox 没有外键、去重约束、body、执行时间、投递状态或审计数据；`due_at` 是 TEXT，而服务期望可与 `timedelta` 相加，转换逻辑未提供。

### 通知 worker 的重命名及影响

工作树删除了被 Git 跟踪的 `src/worker.py`，新增未跟踪 `src/notification_worker.py`；两者字节完全相同，因此这是内容不变的重命名候选，但 Git 尚未提交或暂存该重命名。实现仍在 22:00（含）至 07:00（不含）返回 `defer_until_07_utc`；其他时段发送 body，只捕获 `TimeoutError`，attempt 小于 2 返回 retry，否则 dead_letter。

`tests/test_rules.py` 仍导入 `src.worker`，没有随重命名更新。当前测试在收集阶段以 `ModuleNotFoundError: No module named 'src.worker'` 失败，两个测试都未执行。上一版的“两项通过”只属于上一版完成产物，不能代表当前工作树。README 所说的 separate worker 仍是产品说明；调度、任务认领、attempt 递增、死信持久化和 outbox body 构造均未实现。

### 部署与外部事件证据

`ops/deploy.json` 仍记录 fixture-production 于 2026-09-15T08:00:00Z 部署 `fixture-release-a`，前版为 `fixture-release-previous`，验证仅为 health endpoint，bulk API 未验证。Git HEAD 是本地合成基线，工作树的 48 小时规则和 worker 重命名都没有部署证据；不能把本地变化描述为已上线。

上一版 incident-17 记录 06:55–07:10 UTC 内 4 次通知延迟，并称窗口跨前版和 fixture-release-a。它本轮无法读取，且原文没有事件日期或因果证明；继续作为历史快照保存，不能据此归因给静默规则、批量计划或某次部署。上一版 feature-plan 同样只证明当时快照中的未来计划文本，本轮权限失败未改变项目文档仍明确存在的计划状态。

### 当前 Git 与验证结果

HEAD 仍为 `c25380c7cabf7a294919f92e84ab23e4e66f0793`。`src/api.py` 同时有暂存和未暂存注释；`src/service.py` 未暂存改为 48；`src/worker.py` 未暂存删除；`src/notification_worker.py` 未跟踪；`exports/` 被忽略；两个底稿文件未跟踪。本轮未提交、未暂存，也未修改业务文件。

验证命令为 `PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/bin/python3.13 -m unittest discover -s tests -v`。结果：收集 1 个失败测试模块，0 个业务测试实际执行，原因是旧模块导入在重命名后不存在。未做部署、端到端或事务验证。

## 原文归档

下面每节代码围栏保存对应来源的完整 UTF-8 原文。`current working tree` 与 `current git snapshot` 是本轮现场证据；`previous completion artifact` 只表示从上一版完整产物沿用，未在本轮重新读取外部来源。`coverage.json` 保存同样原文、字节数、SHA-256、来源状态与锚点。

<a id="source-001"></a>

### 1. project:.gitignore

来源：.gitignore  
版本：c25380c7cabf7a294919f92e84ab23e4e66f0793  
证据范围：current working tree  
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
证据范围：current working tree  
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
证据范围：current working tree  
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

### 4. project:docs/product.md

来源：docs/product.md  
版本：c25380c7cabf7a294919f92e84ab23e4e66f0793  
证据范围：current working tree  
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

<a id="source-005"></a>

### 5. project:exports/shift-notes.md

来源：exports/shift-notes.md  
版本：working-tree snapshot; see sha256  
证据范围：current working tree  
SHA-256：`3db2c6bf1dffa3b3c8ef5457e83ad36577bc81631d757402d9f1793f1b80e6fe`  
原文字节：126；完整：是；来源内缺口：无。

````text
# Ignored but in scope
Weekend reminders are currently the largest user complaint.
The next shift starts Monday at 07:00 UTC.
````

<a id="source-006"></a>

### 6. project:ops/deploy.json

来源：ops/deploy.json  
版本：c25380c7cabf7a294919f92e84ab23e4e66f0793  
证据范围：current working tree  
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

<a id="source-007"></a>

### 7. project:src/api.py

来源：src/api.py  
版本：working-tree snapshot; see sha256  
证据范围：current working tree  
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

<a id="source-008"></a>

### 8. project:src/notification_worker.py

来源：src/notification_worker.py  
版本：working-tree snapshot; see sha256  
证据范围：current working tree  
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

<a id="source-009"></a>

### 9. project:src/service.py

来源：src/service.py  
版本：working-tree snapshot; see sha256  
证据范围：current working tree  
SHA-256：`dd4a04d9a9bceac90cc0016b73deaf06b9489ec4e0d0607b193401940efea33e`  
原文字节：966；完整：是；来源内缺口：无。

````text
from datetime import timedelta

POSTPONE_HOURS = 48


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

### 10. project:tests/test_rules.py

来源：tests/test_rules.py  
版本：c25380c7cabf7a294919f92e84ab23e4e66f0793  
证据范围：current working tree  
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

<a id="source-011"></a>

### 11. external:raw:current

来源：../external-full.json  
版本：schema_version=1; collected_at=2026-09-16T10:00:00Z  
证据范围：current local snapshot; source access failed  
SHA-256：`a720ba96264ccb975b87fbff914b18db6b30704efa37c8c88d4da42b5986b093`  
原文字节：514；完整：是；来源内缺口：无。

````text
{
  "schema_version": 1,
  "source_id": "team-wiki",
  "run_id": "REPLACE_WITH_CURRENT_RUN",
  "scope_hash": "REPLACE_WITH_SCAN_SCOPE",
  "status": "unavailable",
  "mode": "full",
  "enumeration_complete": false,
  "permissions_verified": false,
  "next_cursor": null,
  "collected_at": "2026-09-16T10:00:00Z",
  "coverage": {
    "pages": 2,
    "scope": "configured public fixture pages; attachments: none"
  },
  "items": [],
  "deleted_ids": [],
  "errors": [
    "permission denied in synthetic source"
  ]
}
````

<a id="source-012"></a>

### 12. previous:project:docs/new-work.md

来源：docs/new-work.md  
版本：previous working-tree snapshot; now absent  
证据范围：previous completion artifact  
SHA-256：`7e663353f79fa33778148b72f805c1ade8f9951fb940427287906856981e6059`  
原文字节：65；完整：是；来源内缺口：无。

````text
Untracked proposal: configurable postponement. Not yet approved.
````

<a id="source-013"></a>

### 13. previous:external:raw

来源：../external-full.json  
版本：previous completed external export  
证据范围：previous completion artifact  
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

<a id="source-014"></a>

### 14. previous:team-wiki:feature-plan

来源：https://example.org/lantern/feature-plan  
版本：carried forward; not readable this run  
证据范围：previous completion artifact  
SHA-256：`29cd0a58e0b4bb84a4e4cd2aa901db6a464b30d5f3974fca3fdd591d07020721`  
原文字节：157；完整：是；来源内缺口：无。

````text
Approved plan: bulk completion up to 100 tasks with per-task results. This is a plan, not a deployed feature. Multiple-team invitations are still undecided.
````

<a id="source-015"></a>

### 15. previous:team-wiki:incident-17

来源：https://example.org/lantern/incidents/17  
版本：carried forward; not readable this run  
证据范围：previous completion artifact  
SHA-256：`95f59dc2d83f28bc3791ef1e7aeed5f29cce359ddc13fd32c98026a300065070`  
原文字节：192；完整：是；来源内缺口：无。

````text
Observed incident: 4 delayed notifications in fixture-production between 06:55 and 07:10 UTC. The window includes fixture-release-previous and fixture-release-a. No proven causal attribution.
````

<a id="source-016"></a>

### 16. snapshot:HEAD:src/api.py

来源：HEAD:src/api.py  
版本：c25380c7cabf7a294919f92e84ab23e4e66f0793  
证据范围：current git snapshot  
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

<a id="source-017"></a>

### 17. snapshot:INDEX:src/api.py

来源：INDEX:src/api.py  
版本：c25380c7cabf7a294919f92e84ab23e4e66f0793  
证据范围：current git snapshot  
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

<a id="source-018"></a>

### 18. snapshot:HEAD:src/service.py

来源：HEAD:src/service.py  
版本：c25380c7cabf7a294919f92e84ab23e4e66f0793  
证据范围：current git snapshot  
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

<a id="source-019"></a>

### 19. snapshot:INDEX:src/service.py

来源：INDEX:src/service.py  
版本：c25380c7cabf7a294919f92e84ab23e4e66f0793  
证据范围：current git snapshot  
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

<a id="source-020"></a>

### 20. snapshot:HEAD:src/worker.py

来源：HEAD:src/worker.py  
版本：c25380c7cabf7a294919f92e84ab23e4e66f0793  
证据范围：current git snapshot  
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

<a id="source-021"></a>

### 21. snapshot:INDEX:src/worker.py

来源：INDEX:src/worker.py  
版本：c25380c7cabf7a294919f92e84ab23e4e66f0793  
证据范围：current git snapshot  
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

<a id="source-022"></a>

### 22. snapshot:git-status

来源：git-status  
版本：c25380c7cabf7a294919f92e84ab23e4e66f0793  
证据范围：current git snapshot  
SHA-256：`fc71e26dd5cd5610a68edbaf562d3710dd69f0fce4bc49644a0705b2701ec0dd`  
原文字节：122；完整：是；来源内缺口：无。

````text
MM src/api.py
 M src/service.py
 D src/worker.py
?? coverage.json
?? handoff.md
?? src/notification_worker.py
!! exports/
````

<a id="source-023"></a>

### 23. snapshot:git-log

来源：git-log  
版本：c25380c7cabf7a294919f92e84ab23e4e66f0793  
证据范围：current git snapshot  
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

<a id="source-024"></a>

### 24. snapshot:git-diff-unstaged

来源：git-diff-unstaged  
版本：c25380c7cabf7a294919f92e84ab23e4e66f0793  
证据范围：current git snapshot  
SHA-256：`86daf8065cc2210abde8fcfef0912aa0233b32e428d38fe185d5438239914f28`  
原文字节：1051；完整：是；来源内缺口：无。

````text
diff --git a/src/api.py b/src/api.py
index 1e483de..8fb9960 100644
--- a/src/api.py
+++ b/src/api.py
@@ -10,3 +10,4 @@ def handle(method, path, payload, actor, db):
     return {'status': 404, 'error': 'unknown_route'}
 
 # STAGED_FIXTURE_CHANGE
+# UNSTAGED_FIXTURE_CHANGE
diff --git a/src/service.py b/src/service.py
index 3d83e20..1c65510 100644
--- a/src/service.py
+++ b/src/service.py
@@ -1,6 +1,6 @@
 from datetime import timedelta
 
-POSTPONE_HOURS = 24
+POSTPONE_HOURS = 48
 
 
 def owned_task(db, task_id, team_id):
diff --git a/src/worker.py b/src/worker.py
deleted file mode 100644
index c6bdeb7..0000000
--- a/src/worker.py
+++ /dev/null
@@ -1,14 +0,0 @@
-MAX_RETRIES = 2
-QUIET_START_UTC = 22
-QUIET_END_UTC = 7
-
-
-def dispatch(job, clock, transport):
-    hour = clock.hour
-    if hour >= QUIET_START_UTC or hour < QUIET_END_UTC:
-        return 'defer_until_07_utc'
-    try:
-        transport.send(job['body'])
-    except TimeoutError:
-        return 'retry' if job['attempt'] < MAX_RETRIES else 'dead_letter'
-    return 'sent'
````

<a id="source-025"></a>

### 25. snapshot:git-diff-staged

来源：git-diff-staged  
版本：c25380c7cabf7a294919f92e84ab23e4e66f0793  
证据范围：current git snapshot  
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
