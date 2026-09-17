# CLI 与数据契约

目录：命令与状态 → 来源配置 → 外部快照 → 说明 → 导出与恢复。

## 命令与状态

选定 Python 3.10+ 解释器并赋给 `CONTEXT_PYTHON` 后，运行 `"$CONTEXT_PYTHON" "$CONTEXT_SKILL/scripts/context.py" --help` 查看参数。Python 脚本使用标准库，不需要模型 API；它保存和检查材料，详细说明由宿主 Agent 写出。

| 子命令 | 参数 | 输入和有用输出 | 失败时 |
|---|---|---|---|
| `init` | `--project PATH [--state PATH] [--name NAME]` | 创建项目状态与 `config.json`，返回 `state`、`config` | 修正目录或配置；不覆盖其他项目状态 |
| `scan` | `--state PATH` | 创建本轮；返回 `run_id`、`manifest_path`、`source_scopes` | 读取清单错误，保留旧完整版本 |
| `ingest` | `--state PATH --input ENVELOPE.json` | 导入本轮外部全文、附件和完成证据 | 错轮次/范围先重采或重新绑定真实结果，不能伪造哈希 |
| `note` | `--state PATH --input NOTES.json` | 保存说明及其材料指纹关联 | 修正材料键与当前指纹，并实际复核说明 |
| `build` | `--state PATH [--brief FILE] [--max-part-chars N]` | 全文、覆盖报告、必要分卷和附件 | 部分完成仍可审阅，旧完整版本保留 |
| `status` | `--state PATH` | 当前轮次、材料键/指纹、来源状态与缺口 | 没有轮次时先 scan |

`scripts/collect_source.py --state PATH --source ID --output ENVELOPE.json [--resume]` 是可选的内置来源采集命令。它读取已配置来源及当前轮次，输出需要随后 ingest 的快照，不直接发布底稿。退出码 0 表示采集器未发现缺口，2 表示仍有部分结果或缺口，1 表示配置/运行状态错误；仍需检查 JSON 的 status/errors。`--resume` 只复用同轮、同范围已成功响应，累计请求数包括失败请求，不重置预算。

`init` 后按实际项目编辑配置，添加登记来源，再 `scan`。不要把模板整个覆盖到已有配置。新一轮变化从 `scan` 开始；同一轮接续采集不反复调用 scan。

状态默认在项目的 `.project-context/`。`current.json` 的 `run_id` 指向 `runs/<run_id>.json`；读取实际返回路径，不假定用户一定使用默认目录。各轮清单保存项目、工作区、材料、来源、排除项、错误、变化与说明。已成功的内置采集响应保存在 collector-checkpoints；远端缺少稳定快照时先核验版本，再决定是否适合续用缓存。

材料键为 `local:<项目内 POSIX 相对路径>` 或 `<来源 id>:<对象 id>`，如 `local:src/api.py`、`tracker:issue-42`。每个材料有 `fingerprint` 和原文对象引用。复制当前键和指纹来填写说明，不用文件修改时间代替内容版本。

状态目录含项目全文，应保留在项目指定的本地安全位置。不要将整个目录加入通用 Skill 仓库、打印凭证环境变量或自动提交上传。

## 来源配置

`config.json` 基本结构：

```json
{
  "schema_version": 1,
  "project": {"root": "/absolute/project", "name": "project"},
  "local": {
    "exclude": [{"pattern": "scratch/**", "reason": "经确认属于临时非项目材料"}],
    "include_dependencies": false
  },
  "sources": [
    {"id": "project-docs", "kind": "lark", "label": "项目文档", "scope": {"documents": []}}
  ]
}
```

- 保留 init 输出的项目身份与本地默认配置。排除规则写出材料边界依据，不能为得到漂亮完成率而排除未读文件。
- 来源 `id` 唯一且跨轮次稳定；`kind` 是实际来源类型，`scope` 是具体可执行范围。模板中的空列表或占位内容不是完整来源配置。
- 来源除展示标签外的完整配置参与 `scope_hash`。范围、生产窗口、字段、预算或授权约定变化后重新 scan，用新返回值绑定采集结果；不要自行仅对 `scope` 字段计算哈希。
- 生产来源另含 `approval`、`window`、`fields`、`budget`、`read_only`。`approval.confirmed` 与 `read_only.verified` 的真值来自用户授权和实际只读核验，模板默认 false 不能直接改成 true。
- 区分用户已确认的时间规则与本轮具体区间。例如“过去 7 天”不因每次运行而重新授权；本轮 coverage 写有时区的实际起止时间。内置 HTTP 采集器只接受固定 start/end，需在 scan 前按原规则解析窗口并更新配置，保留规则依据，使用本轮新 scope_hash。

## 外部快照 envelope

使用 assets 中模板，字段如下：

| 字段 | 形式与用途 |
|---|---|
| `schema_version` | 固定 `1` |
| `source_id` | 已登记来源 id |
| `run_id` | 当前 scan 返回的轮次 |
| `scope_hash` | 该来源在本轮 `source_scopes` 中的配置指纹 |
| `status` | `complete`、`partial` 或 `unavailable`，依据实际采集 |
| `mode` | `full` 是本次完整清单，`delta` 是变化集 |
| `enumeration_complete` | 范围内所需页和嵌套对象是否枚举完毕 |
| `permissions_verified` | 当前权限和范围是否已核对，缺权限不能写 true |
| `collected_at` | 有时区的实际采集时间 |
| `coverage` | 采集区间、环境、页数、剩余游标、查询定义等；无关字段可省略 |
| `items` | 完整对象数组，见下文 |
| `deleted_ids` | 有明确证据删除的源对象 id；不能填材料键或猜测的消失对象 |
| `errors` | 实际未取回、转换失败、预算耗尽等原因；无错误为空数组 |

`complete` 至少要求枚举完成、权限已核验、`coverage.next_cursor` 为空、`errors` 为空，并满足该来源的额外约束。这些字段是采集证据声明，脚本不能代替 Agent 检查远端确实取完。

每个 item 包含稳定 `id`、`title`、`locator`、`version` 或 `updated_at`。正文在 `content`（全文字符串）与 `content_file`（相对 envelope 目录的文件）中二选一。JSON 返回保留完整已授权字段及结构，不只摘标题、关键词或前几段。

内置采集器的 `collected_at` 是快照封装时间；实际抓取跨度和缓存复用见 `coverage.collection_started_at/collection_finished_at`、`earliest_response_at/latest_response_at` 与 `reused_responses`，不能把旧缓存说成刚刚读取。来源未提供版本时，采集器使用 `sha256:` 内容指纹作为 `version`，它用于内容比对，不代表远端修订号。

可附 `attachments: [{"path": "media/chart.png", "name": "chart.png"}]`。正文文件和附件路径以 envelope 所在目录为基准；使用普通文件及安全相对路径，不使用 `..`、外部绝对路径或符号链接。把已授权附件复制到输入目录，保留稳定对象关联和来源说明后导入。

只使用有助于项目解释的采集元信息；会话标识、认证请求头、签名链接中的秘密、无关账号资料不进入源材料。需要附带未知类型字段时先核对脚本当前支持方式，不假装其会自动生效。

### 删除、权限与分页

`full` 加完整枚举、权限已核验才足以进行集合对账删除。`partial` 和 `unavailable` 保留未出现的旧材料，标明过期。`delta` 删除只能来自明确 `deleted_ids`；当前脚本也要求该增量采集 complete 才应用删除。增量事件流无可靠删除语义时另做全量清单对账。

部分采集中的明确删除会暂存在来源的 `pending_deleted_ids`，同范围后续完整增量完成后应用；后续重新取回同一对象会取消它的待定删除，完整快照则按其权威集合对账并清空待定记录。

一个来源包括 Issue 正文、评论和评审时，每一层分页都纳入完成条件。处理同时间戳和延迟更新时使用来源支持的稳定游标、有界重叠、稳定键去重和必要对账。断在末页也属于未完成，不只看已取得的记录数。

## 详细说明 notes

```json
{
  "schema_version": 1,
  "run_id": "从当前 scan 读取",
  "sections": [
    {
      "id": "technical-api",
      "title": "接口与调用关系",
      "category": "technical",
      "content": "依据实际材料写出的详细 Markdown 说明。",
      "covers": {"local:src/api.py": "从当前清单复制的 fingerprint"}
    }
  ],
  "deleted_ids": []
}
```

`category` 取 `product`、`technical`、`state`、`runtime`、`coverage`。`id` 在项目内稳定；更正同一节复用原 id。notes 中 `deleted_ids` 是废弃说明节的 id，与 envelope 中删除来源对象的字段含义不同。

至少写出 product、technical、state、runtime 四类；coverage 可用于解释冲突、排除和缺口。每份非排除材料有有效说明关联，变化指纹会使旧说明失效，工作区状态变化也会使 state 说明失效。覆盖很多文件的一段泛泛文字不算详细说明，即使程序能数出关联数量。

runtime 说明还绑定来源配置和本轮采集状态：即使正文相同，窗口、环境、权限或采集状态变化也需要重新复核，不沿用旧运行结论。

产品、技术、状态结论绑定真实依据。runtime 或 coverage 没有可用来源时，可以用空 covers 明确写“未采集/未知/不适用及原因”，但不能因此把配置中尚未完成的来源视作完整。

将当前 run 和所有相关材料指纹作为跨模块说明的依据。模型说明变化应审阅原文，不仅把 covers 指纹机械更新。删掉文件后同时检查目录、调用关系、功能状态等相关章节。

## 导出与恢复

`build` 返回 `run_id`、`status`、`document`、`manifest`、`parts`、`attachments`、`latest_complete`、`gaps`。读取实际产物验证，不以返回码正常代替完整性判断。`partial` 产物可审阅，不能替代上次完整版本的状态。

`--brief` 只附加本次文字，不改变材料清单、原文与说明覆盖。省略即不附带旧议题。分卷参数控制交付单卷体量，全文保留；向用户同时提供主稿、分卷和附件对应关系。

恢复同一轮时先读 status、清单和外部采集检查点，接续未完成的来源及说明。需要更换项目配置、工作区已变化或检查点无法对应源版本时重新 scan，新轮复用仍有效材料并重新采集变化来源。旧轮 envelope 不能直接改 run_id 冒充新采集；只有实际核对范围、时间和版本后才组织新轮快照。
