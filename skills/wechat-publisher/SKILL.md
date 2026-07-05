# 微信公众号文章发布 (WeChat Publisher)

将 Markdown 文章一键发布到微信公众号草稿箱，支持图片压缩上传 OSS、自定义排版主题、自动校对。

## 触发关键词

发布微信, 公众号文章, 微信排版, publish wechat, /wechat

## 默认配置

- **默认主题**：落日晚霞（sunset-glow）—— 暖橙红渐变，温暖优雅
- **代码高亮**：atom-one-dark（深色 macOS 终端风格）
- **排版对齐**：左对齐（text-align: left），禁用两端对齐

## 完整工作流

当用户要求发布微信公众号文章时，按以下步骤操作：

### Step 1: 解析文章

用户提供 Markdown 文件路径（可以是手写的、也可以是 wechat-article-writer 生成的）。阅读文件，确认内容正确。

### Step 2: 处理图片

运行图片处理脚本：提取 Markdown 中的远程图片和本地图片 → 用 macOS sips 压缩（max 1600px, JPEG 80%）→ 上传到阿里云 OSS。

```bash
python3 ~/.Codex/skills/wechat-publisher/wechat-publisher/scripts/process_images.py <md_file> <folder_name>
```

参数说明：
- `<md_file>`: Markdown 文件路径
- `<folder_name>`: OSS 上的文件夹名，推荐格式 `YYYY-MM-DD_文章简称`

输出：`image_urls.json`（原始路径 → OSS URL 映射）

**注意**：如果有额外图片未在文章正文中引用（如 16:9 封面图），需要单独上传到 OSS。可以用以下 Python 片段：
```python
import oss2, subprocess, tempfile, os
# 压缩
tmp = tempfile.mktemp(suffix='.jpg')
subprocess.run(['sips', '-s', 'format', 'jpeg', '-s', 'formatOptions', '80', '-Z', '1600', '<src>', '--out', tmp])
# 上传（凭据见 process_images.py 顶部）
auth = oss2.Auth('<KEY_ID>', '<KEY_SECRET>')
bucket = oss2.Bucket(auth, '<ENDPOINT>', '<BUCKET>')
bucket.put_object_from_file('<oss_key>', tmp)
```

### Step 3: 生成发布版

运行文章准备脚本：替换图片 URL 为 OSS URL + 添加 `{width=340}` + 生成 frontmatter。

```bash
python3 ~/.Codex/skills/wechat-publisher/wechat-publisher/scripts/prepare_article.py <md_file> <url_mapping_json> [output_path]
```

输出：`xxx_发布版.md`

**重要：修正宽度属性**

prepare_article.py 会给所有图片添加 `{width=340}`，但实际需求是：
- **横向配图（4:3、16:9 等插画）**：不限制宽度，铺满 → 需手动移除 `{width=340}`
- **UI 截图（通知弹窗、对话框等小元素）**：保留 `{width=340}`
- **竖向配图（9:16）**：保留 `{width=340}`

生成发布版后，必须检查并修正以上宽度属性。

同时检查 frontmatter 的 cover 字段，如果有 16:9 封面图应使用封面图的 OSS URL。

### Step 4: 校对

阅读发布版文章全文，检查：
- 错别字、语病
- 格式问题（标题层级、列表缩进等）
- 图片链接是否都已替换为 OSS URL
- 宽度属性是否正确（横向图铺满、竖向图/截图限宽）
- 列表项是否去掉了装饰性 emoji
- 向用户报告发现的问题，等待确认后继续

### Step 5: 选择主题

默认使用 **落日晚霞（sunset-glow）**。如果用户需要其他主题，可选：

**自定义主题（3 个）：**
| ID | 名称 | 风格 |
|----|------|------|
| `sunset-glow` | 落日晚霞（默认） | 暖橙红渐变，温暖优雅，左对齐，深色代码块 |
| `ink-bamboo` | 墨竹清韵 | 中国风水墨绿，古雅端庄 |
| `starry-geek` | 星空极客 | 深色科技风，紫蓝渐变 |

**wenyan-mcp 内置主题（8 个）：**
default, orangeheart, rainbow, lapis, pie, maize, purple, phycat

用户可选择多个主题，每个主题会生成一篇独立的草稿。

### Step 6: 发布

运行发布脚本：注册自定义主题 → 渲染 HTML → 推送到微信草稿箱。

```bash
node ~/.Codex/skills/wechat-publisher/wechat-publisher/scripts/publish.mjs <md_发布版_file> <theme_ids>
```

参数说明：
- `<md_发布版_file>`: 发布版 Markdown 文件路径
- `<theme_ids>`: 逗号分隔的主题 ID，默认 `sunset-glow`

**常见问题**：
- **IP 白名单错误**（40164）：需要在微信公众号后台 → 设置与开发 → 基本配置 → IP 白名单中添加当前 IP
- **主题不存在**：检查主题 ID 是否在上述列表中

### Step 7: 生成推广文案

发布成功后，生成两个版本的推广文案，保存到文章目录下的 `推广文案.md`：

**版本 1：朋友圈**
- 简短，3-4 段
- 第一行说"写了篇文章，关于 XX"
- 中间分点列出"对你可能有用的场景"（分三种读者：不懂的 / 知道但没深究的 / 已经在用的）
- 附仓库链接（如有开源项目）
- 最后"详细分析见文章👇"

**版本 2：群聊转发**
- 稍长，结构化
- 第一行"分享一篇我写的关于 XX 的文章"
- "背景："一句话说为什么写
- "文章包含："用 📌 分点列出核心内容
- "对你可能有用的场景："用 - 分点列出 3-4 个痛点 → 文章中的对应解法
- 附仓库链接
- "欢迎试用👇"

**语气要求：**
- 参考用户历史推广文案的风格——像跟朋友说"做了个什么、参考了什么、解决了什么、欢迎试用"
- 不要高大上，不要营销腔
- 分段分行，不要一整段话
- 重点是描述对别人的价值，让人明白为什么要看

### Step 8: 发布时间分析 + 投放建议

发布到草稿箱后，**主动**分析文章内容并给出发布时间和投放建议，不等用户问。

**分析维度：**
1. **文章类型**：技术干货 / 工具推荐 / 经验分享 / 观点输出
2. **目标读者**：技术人 / 产品经理 / 泛 AI 爱好者 / 混合
3. **阅读场景**：需要专注阅读 / 可以碎片化浏览

**发布时间建议规则：**
- 技术干货/长文 → **周一至周四早上 8:00-9:00**（通勤学习时间，有讨论情绪）
- 工具推荐/短文 → **工作日午休 12:00-13:00**
- 观点/热点 → 事件发生后 **24 小时内**
- **避开**：周日下午/晚上（没心力）、周五晚上（周末模式）、节假日

**投放建议：**
- 发布和投放**分开**：文章可以提前发，投放等最佳时间
- 朋友圈：跟文章同时或早上发
- 群聊投放：选在目标群最活跃的时间段（通常是工作日上午）
- 不要把所有渠道在同一时间消耗完，可以分批：早上群聊 → 中午朋友圈 → 下午社区

**输出格式：**
```
📅 发布时间建议：
- 文章类型：[技术干货/工具推荐/...]
- 建议发布：[具体日期 + 时间段]
- 理由：[一句话]

📣 投放建议：
- 第一波（[时间]）：[渠道]
- 第二波（[时间]）：[渠道]
```

### Step 9: Git 提交

在微信文章仓库中提交所有变更并推送：

```bash
cd <微信文章目录>
git add .
git commit -m "发布: <文章标题>"
git push
```

## 主题设计规范（落日晚霞 v3 — 2026-03-29）

| 属性 | 值 | 说明 |
|------|-----|------|
| 正文字号 | 16px | |
| 行间距 | 1.85 | |
| 段间距 | margin 22px 0 | 段落呼吸感 |
| 字色 | #3f3f3f | 中灰 |
| 字间距 | 0.5px | |
| 对齐方式 | text-align: left | |
| 标题色 | #1a1a1a | 全部黑色，靠字号区分 |
| h1 | 24px bold | 居中 |
| h2 | 20px bold | 左边框 4px #e67e22 |
| h3 | 18px bold | |
| strong | #1a1a1a bold | 不用强调色 |
| 代码块背景 | #2d2d2d | 圆角8px，max-height 400px |
| 行内代码 | transparent 背景 | 正文色 |
| 引用块 | transparent + #e0e0e0 左边框 | 灰色字 |
| 图片 | 圆角 8px + 居中 | |
| 表格 | 灰色表头 + 左右滑动 | nowrap |
| 分割线 | 橙色渐变但不在正文中使用 | |
| 图片注释 | 居中 + #999 | 0.85em |
| 脚注 | display: none | 不显示 |

## 目录结构

```
~/.Codex/skills/wechat-publisher/wechat-publisher/
├── SKILL.md                          # 本文件
├── scripts/
│   ├── process_images.py             # 图片下载、压缩、上传 OSS
│   ├── prepare_article.py            # 生成发布版 MD
│   └── publish.mjs                   # 注册主题 + 渲染 + 发布草稿箱
└── assets/
    └── themes/
        ├── sunset-glow.css           # 落日晚霞（默认）
        ├── ink-bamboo.css            # 墨竹清韵
        └── starry-geek.css           # 星空极客
```

## 前置依赖

- Python 3 + `oss2` 库: `pip3 install oss2`
- Node.js + `@wenyan-md/mcp` 全局安装
- macOS `sips` 命令（系统自带）

## 凭据

- 阿里云 OSS: 硬编码在 `process_images.py` 中
- 微信公众号: 硬编码在 `publish.mjs` 中（通过 process.env）
