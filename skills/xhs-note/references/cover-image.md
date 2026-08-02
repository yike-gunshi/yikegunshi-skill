# 封面图：先问方向，再写 prompt，最后交给 Codex

风格是作者的偏好，每篇的合适方向也不一样，所以既不写死在这个文件里，也不甩给模型自由发挥。四步走。

## 第一步：出 3 个方向

读完正文，现想 3 个封面方向给他挑。每个方向写清三样：**画面主体**（画什么）、**风格**（什么质感）、**为什么配这篇**。

三个方向要拉开差距，别做成同一张图的三种配色。常用的拉开方式：

- 写实场景（人在具体情境里，代入感强）
- 图形隐喻（把文章的核心关系画成一张图，信息量大）
- 文字海报（大字主导，冲击力强，适合有金句的篇）

已有的视觉参考在 `内容/自媒体/配图风格库/配图风格参考.md`，可以拿来当候选之一，不要当默认。

## 第二步：让他选

用提问的方式给出三个候选，附上简短的画面描述。他选定方向（或者提出第四种）之后再往下走。

**这一步不能跳。** 跳过去自己定方向，等于把他的审美偏好替换成我的。

## 第三步：写生图 prompt

按选中的方向写具体的画面描述，写死到模型不需要再做设计决策：主体、构图、色调、光线、画面里出现的元素和文字，全部说清楚。

prompt 模板：

```markdown
请用你内置的 image_gen 工具生成一张图片，只生成一张。

这是一篇小红书笔记的封面，笔记讲的是：{一句话主题}

画面要求：
{按选中方向写的具体画面描述：主体、构图、色调、光线、画面元素}

三条硬要求：
1. 3:4 竖版构图（1080x1440）
2. 画面上留出位置写标题「{标题原文}」，中文逐字准确、清晰工整
3. 标题文字不要压在人脸或关键信息上

生成完成后告诉我图片保存在哪里。
```

有配图的话一并挂上去，模型看得到实际内容，出来的东西更贴题。

## 第四步：调 Codex

```bash
SCRATCH="<scratchpad>"
_IMAGE_ROOT="${CODEX_HOME:-$HOME/.codex}/generated_images"
CODEX_BIN="$(ls -t "$HOME"/.nvm/versions/node/*/bin/codex 2>/dev/null | head -1)"
[ -x "$CODEX_BIN" ] || CODEX_BIN="$(command -v codex)"

touch "$SCRATCH/img-marker"
env HTTP_PROXY="http://127.0.0.1:39178" \
    HTTPS_PROXY="http://127.0.0.1:39178" \
    NO_PROXY="localhost,127.0.0.1,::1" \
    "$CODEX_BIN" exec --skip-git-repo-check \
      -i "配图1.png" -i "配图2.png" \
      "$(cat "$SCRATCH/cover-prompt.md")"

find "$_IMAGE_ROOT" -type f -name "*.png" -newer "$SCRATCH/img-marker"
```

`-i` 可以重复；纯文字的笔记不带 `-i`。

用默认推理档跑就行，因为 prompt 已经写死，模型不需要做设计决策。**反过来，把设计决策留给模型自己（brief 里写"画面你来定"）会在默认的 high 档下卡死**，实测挂到 17 分和 29 分、日志全空、一张图没出。这也正是方向要先问作者、prompt 要先写好的原因：既拿到了他要的风格，又避开了那个坑。

生成的图落在 `~/.codex/generated_images/{thread_id}/`。用 marker 文件加 `find -newer` 捞出这次新增的那张，复制到笔记目录，原图留在那儿。

单次十分钟上下，放后台执行。超过 15 分钟既没出图也没日志就是挂住了，杀掉重跑。

## 环境前置条件

上面脚本里这三处都是有原因的，换写法之前先看一眼：

1. **用二进制的绝对路径调用**。`codex` 在 .zshrc 里是个 shell 函数，非交互 bash 加载不到函数定义
2. **挑 nvm 下的那份 codex**（脚本里的 `ls -t` 就是干这个的）。它跟得上 config.toml 里的 `model` 和 `service_tier` 设置，`/usr/local/bin/codex` 那份版本落后，会以"requires a newer version"拒掉
3. **代理走本机 Clash 的 127.0.0.1:39178**。codex 要连 `wss://chatgpt.com/backend-api/codex/responses`，这个出口连得上。.zshrc 里给 codex 配的是 Decodo ISP 出口，那条通道到这个 websocket 端点会被 connection reset

卡住时的排查顺序：先做冒烟测试 `codex exec -c model_reasoning_effort="low" "只回复两个字：正常"`，半分钟内该返回。回得来说明网络和版本都没问题，问题在 prompt；回不来才去查代理和二进制。

生不出来时降级：把 prompt 存成 `封面.prompt.md` 留在笔记目录，明确说"封面待生成"。

## 出图后

- 存两份：`最终配图/00-封面.png`（发布用）和 `图片/封面.prompt.md`（重生成用）
- 中文标题逐字核对，生图模型偶尔会吞字或写错笔画
- 不满意就把不满意的点写进 prompt 再跑一次（"人物换成俯视视角""少一点文字元素"），同一段 prompt 跑两次结果也不一样
