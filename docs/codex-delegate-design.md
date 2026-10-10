# 《codex-delegate Skill 设计文档》

> 阶段：S4 实测完成 · 状态：已实现并安装（2026-10-10，待决策项均按倾向执行）
> 档位：轻档 + 脚本（自用；但派活每天发生、坑会复发，所以配确定性脚本，S4 用一个真实小任务跑对照）
> 日期：2026-10-10
> 参考：[LearnPrompt/partner-skill](https://github.com/LearnPrompt/partner-skill) v2.0.1（MIT）

## 0. Skill 化决策（S0 结论）

用户已定分工：所有代码由 Codex 写，Claude 负责编排、文档、验收（记忆 `codex-cli-backend-delegation`，0715 起）。可每次派活靠的是散落在记忆和 [codex-exec-调用手册](../../../知识/工具手册/codex-exec-调用手册.md) 里的命令片段，每次重新拼：App 版二进制、Clash 代理、`< /dev/null`、60–90 秒查会话文件判活、worktree 里沙箱提不了 commit。返工时还会重开会话，让 Codex 重读一遍 worktree。forge-eng / forge-bugfix / forge-design-impl 三个 skill **完全没提 Codex**，这条分工只存在于记忆里。

替代方案和代价：
- **只补手册**：手册是参考资料，没法执行；作业状态、resume、判活还是每次手工拼。
- **写进 forge-eng**：forge 是双宿主的（在 Codex 里也会跑），把「Claude 派给 Codex」写进去，在 Codex 宿主里就是错的；而且要改三个 skill，各写一遍。
- **直接装 partner-skill**：它围绕「省 Claude API 费用」设计，自带 `.partner/goal.md`、receipt、配置 UI，和 forge 的文档入口、ship 流程重复，触发词还会和 forge-eng 抢活。

所以做成独立的窄 skill：forge 三个 skill 各加一行引用，宿主不是 Claude Code 时不生效。

满足的资格条件：☑ 会重复使用 ☑ 有脚本能省重复劳动 ☑ 需要跨会话统一 ☑ 容易被路由错（和 forge-eng、生图走 codex 的规则相邻）

## 1. 收料结论（S1，从历史提取）

### 1.1 需求与场景

- **使用者与处境**：Claude Code（宿主）在 forge-eng / bugfix / design-impl 进入写代码阶段时；用户本人只看结果。
- **现在怎么做、哪一步最烦**：手拼 `env 代理 + App 二进制 codex exec -s workspace-write -C <wt> "..."`，后台跑，靠查 `~/.codex/sessions` 判活；返工重开；验收靠 Claude 自觉。
- **理想产出**：一条命令派活，作业状态落盘可查；卡住能自动发现；返工接回原会话；验收有固定判据；通过后 Claude 提交。
- **什么算做对了**：① 派出的作业不会因 stdin、代理、二进制原因卡死或失败；② 「DONE 但没改东西」能当场识别；③ 返工走 resume，不重开；④ 验收对照任务书，不只看 diff；⑤ 两轮不过就收回，不无限返工。

### 1.2 已有决策与约束

| 类别 | 内容 | 可否推翻 |
|---|---|---|
| 分工 | 代码一律交 Codex，Claude 写文档、prompt，负责验收与提交 | 已拍板（用户 0715） |
| 二进制 | `/Applications/ChatGPT.app/Contents/Resources/codex`，`/usr/local/bin/codex` 太旧 | 环境事实 |
| 网络 | 走 Clash `127.0.0.1:7897`，不走 shell 里 `codex()` 函数的 Decodo | 环境事实 |
| 模型与档位 | 遵循 `~/.codex/config.toml` 和会话设置，不写死、不因个别超时降档（工作区 CLAUDE.md） | 已拍板 |
| 后台运行 | 一律 `< /dev/null` | 环境事实（0802 根因） |
| 代码改动位置 | 只在 worktree 里改（info2action CLAUDE.md §3） | 已拍板 |
| 文档入口 | 不新建平行任务表；作业状态是临时产物，结论回写 ENGINEERING.md 或 BF 报告 | 已拍板 |

| 参考 | 借鉴什么 | 明确不借鉴什么 |
|---|---|---|
| partner-skill `delegate-codex.sh` | 作业目录结构（prompt / log.jsonl / meta / stderr）、`submit/status --wait/result/resume/cancel` 五个子命令、`--json` 事件流判活、`codex exec resume` 接回会话 | 身份矩阵 / role / config.toml 解析（约 40% 代码）、`--host` 双宿主、PARTNER_* 环境变量链 |
| partner-skill 任务书模板 + fable5-principles | 先讲为什么、一句话任务、可验证的验收标准、「只在不可逆或超范围时停」的检查点、「不许废话，结尾最多 3 行心得」 | 「省 API 钱」的执行通道排序表 |
| partner-skill claude-driven Phase 3/4 | DONE ≠ 干活、按任务书验收、两轮上限再收回 | `/loop` 必用（短任务直接阻塞等）、goal.md 任务表、receipt |
| partner-skill arbiter 协议 | 盲解仲裁：同题原样给两方，互不可见，污染即重跑 | 三身份配置、same-vendor 标注 |
| partner-skill 其余部分 | — | 配置 UI、receipt、showcase、bounded planning、goal-to-pr、idea-king（如需另外单独装） |

## 2. 设计

### 2.1 要解决的问题

替 Claude 把「拼命令派活 → 判活 → 收结果 → 返工 → 验收 → 收回」这条每天重复、坑会复发的链路，固化成一个脚本加一套判据。

### 2.2 定位与边界

**定位**：Claude 写代码阶段的派活协议。像一个**严格的总包**：任务书写清楚才发；工人说「做完了」不算数，要看现场（diff 和门禁）；返工就叫原班人马回来改，不换人从头读图纸；两次改不好就自己上手。

**核心立场**：Codex 的产出要 Claude 签字才算数。所以每一步都留证据（作业目录），验收的标准是任务书，不是 diff 自洽。

**范围**：给定一个 worktree 和一份或几份任务书，派给 Codex 执行，收回可提交的改动。一次处理一个 feature 或一个 BF 下的若干任务。

**不处理**：

| 不处理什么 | 交给谁 |
|---|---|
| 需求、设计、拆任务本身 | forge-prd / forge-design / forge-eng（本 skill 只接拆好的任务） |
| 生图 | 全局 CLAUDE.md 的 codex image_gen 规则（调用相同，但不需要验收和返工这套） |
| 宿主已经是 Codex | 直接干活，不嵌套 `codex exec`（工作区 CLAUDE.md） |
| 用 Codex 做代码审查 | forge-review / `/code-review`；仲裁只用于结论有争议时 |
| 提交、推送、合并 | forge-ship；本 skill 停在「验收通过，Claude 已提交到 worktree 分支」 |

**很像但不该触发的 query**：
1. 「用 codex 生成一张架构图」→ 生图规则
2. 「codex exec 卡住了，为什么」→ 排障，看调用手册的判死活一节就够，不派新活
3. 「帮我在 Codex 里 review 一下这个 PR」→ forge-review
4. 「把 forge-eng 的拆任务方式改一下」→ 改 skill，走 skill-build
5. （宿主是 Codex 时）「实现这个接口」→ 直接写

### 2.3 触发与意图路由

**触发层素材**
- 应触发：「这几个任务派给 codex 跑」「让 codex 实现 T03，你验收」「codex 后台跑完你全量 review」「上次那个 codex 作业返工一下」「这个根因判断有争议，让 codex 盲解一遍」；以及 forge-eng/bugfix/design-impl 进入写代码步骤时（由它们的引用触发，用户可能完全没提 codex）
- near-miss：上面 5 条
- 可能抢活的隔壁：forge-eng（它负责拆任务和 ENGINEERING.md，本 skill 只接执行环节）

**路由层**

| 意图 | 信号 | 应答 |
|---|---|---|
| 派新活 | 有 worktree + 有未执行的任务 | 全流程：写任务书 → submit → 判活 → 验收 |
| 续作业 | 提到已有 jobId，或「返工」「接着跑」「看下 codex 进度」 | 跳到 status / resume，不重新派 |
| 仲裁 | 「有争议」「盲解」「second opinion」，或 bugfix 根因有两种都说得通的解释 | 走仲裁协议，不改代码 |

### 2.4 输出框架

每次派活收尾，Claude 给用户（并回写 ENGINEERING.md 或 BF 报告）一段**派活小结**，固定四段：

1. **作业表**：jobId / 任务 / 状态（通过 / 返工 n 轮后通过 / 收回）/ 耗时
2. **验收证据**：每个任务对照任务书逐条打勾，加门禁命令及结果
3. **异常**：卡死重拉、DONE 但 diff 为空、收回原因；没有异常就写「无」
4. **提交**：commit hash，或「未提交（原因）」

触发式：仲裁时多一段「两方结论 / 分歧点 / 裁定理由」。

### 2.5 执行流程

| 步 | 做什么 | 工具 | 失败怎么办 |
|---|---|---|---|
| 0 预检 | 确认宿主是 Claude Code，在 worktree 里；`git status --short` 记下改动前的基线 | git | 不在 worktree → 停，按项目 CLAUDE.md 先建 |
| 1 写任务书 | 按 `references/packet.md` 写到 `.forge/jobs/<label>.prompt.md` | Write | 写不出可验证的验收标准 → 说明任务没拆好，退回 forge-eng |
| 2 派活 | `delegate.sh submit --repo <wt> --prompt-file ... --label T03`；互相独立的任务可并行 | 脚本 | submit 报错（二进制、代理）→ 跑冒烟测试，按手册排查顺序处理 |
| 3 判活 | 短任务 `status --wait --timeout 600`；长任务或多个作业用 `/loop` 每 5 分钟查一次 | 脚本 | 90 秒内没有任何 JSONL 事件 → cancel 后重派一次（启动卡死重拉即好）；中途连续 10 分钟无新事件 → 读 stderr，cancel 后重派或收回 |
| 4 收结果 | `result <id>` 读最后一条消息；`git diff` 比对基线 | 脚本 + git | DONE 但 diff 为空 → 异常：先查 stderr 里有没有沙箱拦截，再判断是 Codex 认为「已经做完」还是没做；不要盲目让它再试一次 |
| 5 验收 | 逐条对照任务书的验收标准，读完整 diff，跑门禁 | git、项目测试 | 不过 → 写修改意见，`resume <id> --prompt-file fix.md`，最多两轮 |
| 6 收回 | 两轮不过，或 Codex 明确卡在需要判断的地方 → Claude 自己改完 | — | 在小结里写明收回原因 |
| 7 提交 | Claude 在 worktree 里提交；作业目录不进 git（`.forge/` 已在 gitignore 里） | git | — |

**仲裁协议**（触发式）：同一问题原样写两份，一份交 Claude 子 agent（或主会话先独立作答并封存），一份 `submit --read-only` 交 Codex；两份都不许含对方的答案或倾向；一致就采纳，不一致由 Claude 裁定并写明分歧点。发现污染就重跑，不打补丁。

### 2.6 辅助资源

| 资源 | 类型 | 为什么 |
|---|---|---|
| `delegate.sh` | scripts/ | 五个子命令；钉死二进制、代理、`< /dev/null`、`--json`、`-s workspace-write`；状态落在 `<repo>/.forge/jobs/<id>/` |
| `packet.md` | references/ | 任务书模板，写任务书时读 |
| `acceptance.md` | references/ | 判活阈值、DONE ≠ 干活、返工意见怎么写、收回判据，验收时读 |
| `arbiter.md` | references/ | 仲裁协议，只在仲裁时读 |

### 2.7 输入输出定义

**真实 query 样本**：
1. 「forge-eng 拆出来 T01–T04 了，T01/T02 互不依赖，并行派给 codex，worktree 在 `.worktrees/ai-search-mvp`」
2. 「codex 那个 T03 跑了二十分钟还没动静，看下是不是挂了」
3. 「T02 验收没过，`test_ai_search_quota` 两个用例挂了，让它原会话改」
4. 「BF-1009-2 根因我觉得是连接池会话污染，但也可能是 read model 没刷新，让 codex 盲解一遍再定」
5. 「这个前端样式改动按 DESIGN.md 模块 28 实现，交给 codex，你截图验收」
6. 「上次 codex 作业 20261009-ab12 收尾一下，给我派活小结」

**预期输出**：一个已提交（或明确说明为什么没提交）的 worktree 分支，加上 2.4 的派活小结。

### 2.8 上下文分层规划

| 层 | 放什么 | 预估体量 |
|---|---|---|
| description | 派活、返工、仲裁的触发词；「forge 写代码阶段即使用户没提 codex 也用」；排除生图和 Codex 宿主 | ~400 字符 |
| SKILL.md 正文 | 定位、预检、7 步骨架、红线、小结骨架 | ~120 行 |
| references/ | packet.md、acceptance.md、arbiter.md | 各 40–80 行 |
| scripts/ | delegate.sh | ~200 行（partner 版 544 行，删掉身份和配置机制） |

## 3. 完备性门禁自查

| # | 检查项 | 通过 |
|---|---|---|
| 1 | ≥3 个很像但不该触发的 query | ☑ 5 个 |
| 2 | 不处理什么、交给谁 | ☑ |
| 3 | 必出模块对应考点（轻档豁免） | ☑ 小结四段对应 1.1 的五条「做对了」 |
| 4 | tool 字段（轻档豁免） | — |
| 5 | ≥5 条真实 query | ☑ 6 条 |
| 6 | 失败怎么办 | ☑ 每步都有 |

## 4. 待决策项

| # | 问题 | 我的倾向 | 状态 |
|---|---|---|---|
| 1 | 放哪个仓库 | `Skill/yikegunshi-skill/skills/codex-delegate`（个人仓库）。它绑定本机环境（二进制、代理），不适合放进双宿主的 forge-skills | 待定 |
| 2 | 沙箱档位 | 脚本固定 `-s workspace-write`（只能写 worktree），不用 config 里的 `danger-full-access`；代价是 Codex 提交不了，由 Claude 提交，正好是验收关口 | 待定 |
| 3 | 脚本谁写 | 按你的分工规则交 Codex 写，以 partner 的脚本为参考并保留 MIT 署名；Claude 写 SKILL.md 和 references 并验收脚本。这也是本 skill 的第一次实战 | 待定 |
| 4 | forge 三个 skill 怎么接入 | 在 forge-eng / forge-bugfix / forge-design-impl 写代码那一步各加一行：「宿主是 Claude Code 时，代码实现走 codex-delegate」。改之前先快照；等 S4 通过后再改 | 待定 |
| 5 | 判活阈值 | 启动 90 秒无事件就重拉；运行中 10 分钟无新事件算异常（手册记录的高档位静默长尾 p95 约 1 分钟、最长 30 分钟，10 分钟偏保守，异常时先读 stderr，不直接杀） | 待定 |
| 6 | S4 验证用什么任务 | 挑一个真实的小改动（比如 TODO 里一条小 bug 或测试补全），完整走一遍：派活 → 判活 → 故意让验收不过触发一次 resume → 提交；不另造假任务 | 待定，需你指一个或我从 TODO 挑 |
