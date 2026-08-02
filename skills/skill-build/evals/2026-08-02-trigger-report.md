# skill-build 触发评测报告 · 2026-08-02

首轮基线。评测对象是 `skill-build` 的 description，题集 `evals/trigger-eval.json`。

## 怎么跑的

`claude -p <query> --output-format stream-json --max-turns 1`，从 stream 里抓
`tool_use(name=Skill)` 并读 `input.skill`，判定是否命中目标 skill。在真实工作区里跑，
所以 `available_skills` 是完整的 26 个，路由竞争是真实的。

两轮，工具可见性不同：

| 轮次 | 工具集 | 规模 | 花费 |
|---|---|---|---|
| A | 仅 `Skill` | 20 题 × 3 次 = 60 run | $13.83 |
| B | `Read Grep Glob Skill TodoWrite` | 10 条正例 × 1 次 = 10 run | 约 $2 |

## 轮次 A 结果：train / test 均 100%

| 集合 | TP | FP | FN | TN | 准确率 | 召回 | F1 |
|---|---|---|---|---|---|---|---|
| 全部 | 30 | 0 | 0 | 30 | 100% | 100% | 100% |
| train | 18 | 0 | 0 | 18 | 100% | 100% | 100% |
| test | 12 | 0 | 0 | 12 | 100% | 100% | 100% |

10 条 near-miss 负例全部 0% 误触发，且各自被正确的 skill 接走：

| 负例去向 | 次数 |
|---|---|
| 未调 skill，直接回答 | 16 |
| prompt-craft | 5 |
| lark-export | 3 |
| book-to-mindmap | 3 |
| xhs-note | 3 |

n1（写个判情绪的 prompt）稳定路由到 prompt-craft，说明 2026-08-02 补的
skill-build ↔ prompt-craft 双向排除项生效了。

## 轮次 B 结果：正例召回掉到 80%

**轮次 A 的 100% 是被工具限制抬上去的。** 只给 `Skill` 一个工具，等于抹掉了
"我自己动手就行"这条路，而那恰恰是 SKILL.md 里写明的欠触发机制——
模型只在自己搞不定的任务上才去查 skill。

放开只读工具后：

| id | 结果 | 模型改用了什么 |
|---|---|---|
| t1–t8 | 触发 | Skill |
| **t9** | **未触发** | Read + Bash |
| **t10** | **未触发** | Bash |

- t9：`skill 里那些 references 和 scripts 到底该怎么分？我现在全塞 SKILL.md 里了，一千多行`
- t10：`我这两个 skill 老互相抢活，用户问 A 的事结果 B 跳出来了。边界该怎么划`

两条都是"诊断已有 skill"这一族。模型判断"我读一下他的 skill 目录就能回答"，
于是绕过了 skill。

**结论：真实工具可见性下的正例召回是 8/10，不是 10/10。** 后续任何优化都以 80% 为基线。

## 归因与尚未采取的动作

description 里"改已有 skill"那段列了：不触发、触发错了、写得太长、红线堆太多、
description 要重写、要补 references/scripts、要做评测或基线对照、要判断某段约束该不该删。

t9 问的是**分层决策**（什么该外移），与"要补 references/scripts"字面接近但语义不同；
t10 问的是**路由边界划分**，整段里没有对应表述，最近的只有"触发错了"。

**没有据此改 description。** t9 和 t10 都在 test 集里，用它们调 description 正是
train/test 分割要防的过拟合。要修得先在 train 侧补同族题、在那里复现失败，
再改，再用未被污染的 test 集验收。

## 已知的方法学缺陷

1. **轮次 B 只跑了 1 次/题**，没有 3 次取率，t9/t10 的失败可能含随机성分。
2. **轮次 B 没跑负例**。工具变多通常只会降低触发率，精确率应当不会变差，但没实测。
3. **`Bash` 出现在 tool_use 里但不在 allowedTools 中**——记录的是模型的意图而非成功执行，
   对触发判定无影响（它确实没选 Skill），但说明工具集约束并未完全约束模型的第一选择。
4. 单模型单次快照，未跨模型验证。

## 复现

```bash
scratchpad/run_trigger_eval.sh evals/trigger-eval.json skill-build 3 results.tsv 3
scratchpad/score_trigger.py results.tsv evals/trigger-eval.json
```
