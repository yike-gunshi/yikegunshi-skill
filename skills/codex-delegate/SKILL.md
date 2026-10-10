---
name: codex-delegate
description: Claude Code 把代码实现派给本机 Codex CLI 后台作业：写任务书、派活、判活、收结果、按任务书验收、返工接回原会话（最多两轮）、收回、提交。用户说"派给 codex""让 codex 实现，你验收""codex 后台跑""codex 作业返工/看进度""这个结论有争议，让 codex 盲解一遍"时用；forge-eng、forge-bugfix、forge-design-impl 进入写代码步骤时也用——哪怕用户没提 codex。不处理：codex 生图（全局生图规则）、宿主本身就是 Codex（直接写）、代码审查（forge-review）、拆任务（forge-eng）、合并发布（forge-ship）。
---

# codex-delegate — Claude 编排，Codex 写代码，Claude 签字

把拆好的任务派给 Codex 后台执行，收回一份已提交、并对照任务书验收过的 worktree 改动，外加一段派活小结。

## 定位与边界

像一个**严格的总包**：任务书写清楚才发；工人说「做完了」不算数，要看现场（diff 和门禁）；返工叫原班人马回来改，不换人从头读图纸；两次改不好就自己上手。

核心立场：Codex 的产出要 Claude 签字才算数。用户把代码交给 Codex，是因为 Claude 守住验收这道关；所以每一步都留证据（作业目录），验收的标准是任务书，不是「diff 看起来自洽」。只看 diff 的验收会把规格偷换成「改了的部分没毛病」，从而漏掉根本没做的任务。

边界外的交出去：拆任务和 ENGINEERING.md 归 forge-eng；生图走全局 CLAUDE.md 的 codex image_gen 规则（调用相同，但不需要验收返工这套）；宿主就是 Codex 时直接写，不嵌套 `codex exec`；审查交给 forge-review；推送合并交给 forge-ship。

## 按需读取

| 文件 | 什么时候读 |
|---|---|
| `references/packet.md` | 第 1 步写任务书前 |
| `references/acceptance.md` | 第 3–6 步：判活异常、收结果、验收、写返工意见、决定收回时 |
| `references/arbiter.md` | 只在仲裁时读 |

脚本 `scripts/delegate.sh`（下称 `D`）：`D=~/.claude/skills/codex-delegate/scripts/delegate.sh`。改过脚本后跑 `scripts/selftest.sh`，看到 `SELFTEST PASS` 再用。

## 意图分流

| 意图 | 信号 | 走哪 |
|---|---|---|
| 派新活 | 有 worktree，有尚未执行的任务 | 第 0–7 步 |
| 续作业 | 提到 jobId，或「返工」「接着跑」「看下 codex 进度」 | `D list` 找到作业，从第 3 或第 5 步接上，不重新派 |
| 仲裁 | 「有争议」「盲解」「second opinion」，或根因有两种都说得通的解释 | 读 `references/arbiter.md`，不改代码 |

## 第 0 步 预检

- 确认自己是 Claude Code（宿主是 Codex 就停，直接写）。
- 确认在任务所属的 worktree 里（项目 CLAUDE.md 要求代码只在 worktree 改）。不在就先按项目规则建或复用。
- `git status --short` 看一眼：有别人的未提交改动就先说明，避免和 Codex 的改动混在一起。脚本会自己记基线，但人要知道基线里有什么。
- 第一次在本会话派活时跑 `D doctor`：二进制路径会随 App 更新挪位置，代理也可能掉线，先排除环境问题。

## 第 1 步 写任务书

按 `references/packet.md` 写到 `<worktree>/.forge/jobs/<label>.prompt.md`（`.forge/` 不进 git）。一个任务一份，label 用 forge-eng 的任务编号（T03）或 BF 编号。

写不出可验证的验收标准，说明任务没拆好，退回 forge-eng 重拆，不要把模糊的活扔给 Codex 让它猜。

## 第 2 步 派活

```bash
JOB=$($D submit --repo "$WT" --prompt-file "$WT/.forge/jobs/T03.prompt.md" --label T03)
```

- 互相独立的任务可以并行提交；有依赖的按顺序，等前一个验收通过再派下一个，否则后一个会建在没验收的地基上。
- 只读扫描、调研、仲裁加 `--read-only`。
- 模型和推理档位默认跟随 `~/.codex/config.toml`，只有任务确实需要时才传 `--effort`。不要因为上次超时就降档：高档位首个输出前的静默期本来就可能很长。

## 第 3 步 判活

- 单个短任务：`$D status $JOB --repo "$WT" --wait --timeout 900`，阻塞等结果。
- 长任务或多个作业：用 `/loop` 每 5 分钟对每个作业跑一次 `status`，全部进入终态后停掉 loop，进入第 4 步。
- 状态异常（`STALL_START`、`IDLE`、`FAILED`）按 `references/acceptance.md` 的判活表处理。总原则：启动卡死就重派一次，运行中静默先读 stderr 再决定，不要见静默就杀。

## 第 4 步 收结果

`$D result $JOB --repo "$WT"`：打印 Codex 的最终回复和相对基线的改动。

出现 `WARNING: EMPTY_DIFF` 或 `SANDBOX_BLOCK` 时不要直接返工，先按 `references/acceptance.md` 判清原因。让它「再试一次」只会白烧一轮。

## 第 5 步 验收

逐条对照任务书的验收标准，读完整 diff（`git diff` 加新增文件），跑任务书里写的门禁。前端改动要看真实页面：截图或 forge-qa。

不过就写返工意见（写法见 `references/acceptance.md`），发回原会话：

```bash
JOB2=$($D resume $JOB --repo "$WT" --prompt-file "$WT/.forge/jobs/T03.fix1.md")
```

然后回到第 3 步。resume 让 Codex 带着上一轮的上下文改，不用重读仓库。

## 第 6 步 收回

同一任务返工两轮还不过，或者 Codex 明确卡在需要产品判断的地方，就由 Claude 自己改完。第三轮返工的边际收益通常已经低于 Claude 直接动手，而且问题往往出在任务书本身。收回原因写进小结，它是下次拆任务的输入。

## 第 7 步 提交与小结

Codex 跑在 `workspace-write` 沙箱里，提交不了 worktree 的 commit，所以由 Claude 提交：这也是 Claude 签字的时刻。一个任务一个 commit，message 里注明 `impl: codex (job <jobId>)`。

然后输出派活小结，同时回写 ENGINEERING.md 对应任务行或 BF 报告：

```
## 派活小结

| jobId | 任务 | 结果 | 轮次 | 耗时 |
|---|---|---|---|---|
| 20261010-1412-T03 | ... | 通过 / 返工 1 轮后通过 / 收回 | fresh+r1 | 14m |

**验收证据**
- T03：☑ 标准 1 … ☑ 标准 2 …；门禁 `<命令>` → <结果>

**异常**：<卡死重派、EMPTY_DIFF、收回原因；没有就写「无」>

**提交**：<commit hash>，或「未提交：<原因>」
```

仲裁时在异常之后加一段：两方结论 / 分歧点 / 裁定理由。

## 红线

1. **不替 Codex 的产出签空字**：没读 diff、没跑门禁，就不提交、不在小结里写「通过」。用户把代码交出去的前提是这道关还在，一次空签就会让后面所有「通过」失去意义。
2. **派活不越权**：任务书里不让 Codex 推送、部署、改 `.env`、动生产数据库或跑破坏性 git 操作。这些在项目 CLAUDE.md 里需要用户单独授权，Codex 跑在 `approval_policy=never` 下，没有人会拦它。
