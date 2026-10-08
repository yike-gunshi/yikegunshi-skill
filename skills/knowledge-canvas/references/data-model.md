# 一份数据驱动画布与文档

数据是 JSON，所有名称与示例均替换为本次材料。字段不携带 HTML、CSS 或可执行函数，文本由模板安全渲染。

## 生成与检查

```sh
node scripts/build_canvas.cjs material.json output.html
node scripts/check_canvas.cjs output.html --channel chrome
```

build_canvas 使用同目录的 assets/canvas-template.html，不依赖项目路径或外部服务。输出文件已存在时默认拒绝；明确要更新该产物时加 `--overwrite`。脚本只生成本地 HTML，不安装、发布或同步其他副本。

Playwright 按环境正常安装或通过 `--playwright /absolute/path/to/playwright` 指定；截图通过 `--screenshot-dir /existing/directory` 保存。`--feishu` 额外检查保守大小边界，不执行写入。`--motion-check` 使用实际截图对比静态节点，需可加载 pngjs（`--pngjs` 可指定路径）。

模板自身含流程型虚构示例，可直接打开；概念型数据在 assets/concept-example.json。两者用于复用与回归，不作为真实材料依据。

## 顶层

| 字段 | 含义 |
|---|---|
| `meta.title`、`meta.subtitle` | 标题与范围说明 |
| `meta.mode` | `process`、`concept`、`mixed`，影响默认 Tab 名称，不替代关系判断 |
| `meta.version` | 可选，资料版本或日期，不等于已部署 |
| `meta.canvasLabel` | 可选覆盖画布 Tab 名称 |
| `meta.reserveFAQ` | 默认 false，空 FAQ 只有明确预留时显示 |
| `width`、`height` | 画布坐标范围 |
| `groups`、`nodes`、`edges` | 分组、节点、完整语义关系 |
| `connectors` | 可选，汇合线等仅用于绘制的公共线段，不冒充新的功能节点 |
| `motion.steps` | 可选，按顺序排列的 edge ID 数组，每一步数组内部并行 |
| `faq` | 问题数组，每项含 question、answer，可有 nodeIds 和 source |

ID 用小写英文、数字、连字符或下划线，首字符为字母，在对应集合中唯一。group 和 node 共用定位空间，不能重名。坐标是有限数，宽高为正。数据中的英文名必须来自材料，ID 不等于对外调用名。

## 分组与节点

分组：`id, title, summary, parent?, color, x, y, w, h`。parent 指向已有分组，不成环。颜色使用 `cyan, green, violet, amber, slate` 之一，在同一图中保持语义稳定。

节点：`id, group?, title, summary, english?, shape, x, y, w, h, explanation, samples, sources?`。

- shape：`process, decision, document, database, text`
- status 可选：`{kind, label}`，kind 为 `conditional, disabled, default-off, unverified`，只有 disabled 置灰
- explanation：`[{label, body}]`，body 是文本或列表
- 列表项：文本，或 `{text, children:[...]}`，用于真实的多层说明
- sources：来源说明字符串数组，可包括相对文件、页码、URL、版本等，默认作为文本呈现

```json
{
  "explanation": [
    {"label":"用途","body":"保留资料中可核验的结论"},
    {"label":"处理","body":["读取原文",{"text":"核对来源","children":["对应章节","已提供的版本"]}]}
  ],
  "samples": [{
    "title":"一个构造例子",
    "type":"构造示例",
    "source":"本模板的虚构资料",
    "blocks":[{"label":"原文","format":"text","raw":"这是一段完整的示例原文。"}]
  }]
}
```

samples 可以为空，但需在 explanation 或 sources 中明确证据缺口。不要编造示例来满足字段检查。

## 样例原文

每个 block 使用 `label, format, raw`，raw 始终为字符串。format 支持 `json, text, code, markdown, quote, math`。只有 JSON 才校验语法，**不将解析后的值用于回写、展示或复制**，避免大整数、空格和键顺序发生变化。

JSON 样例的两个块可命名“输入 JSON”和“输出 JSON”；概念样例可命名“例子”和“反例”。未知结果不填假返回值。公式按原始文本呈现，需要公式排版时再评估对应渲染支持。

构建器只替换 `<script type="application/json" id="canvas-data">` 的数据，并把 `<` 安全编码，防止样例中的结束标签逃逸。节点、文档与 FAQ 的字符串均通过 textContent 或可靠转义显示。

## 关系与汇合线

edge：`id, from, to, relation, importance, points, label?, labelAt?, arrow?`。

- from/to 指向 node 或 group，保留完整真实关系
- relation：`flow, data, dependency, composition, condition, loop, reference`
- importance：`primary, secondary, auxiliary`，auxiliary 默认隐藏；不要由 relation 自动推导
- points 是实际连接端点的正交折线路径，至少两个点，标签位置单独维护
- arrow 默认 true，组成支线可设 false
- renderPoints 可选，汇合时只绘制不重复的支线，完整关系仍由 points 保留

生成器通过 `scripts/route_geometry.cjs` 校验端点接边、法向方向、首尾直线和过密折点，失败时拒绝生成。`check_canvas.cjs` 另核对实际 SVG 终点、圆角后的末段与箭头参考点。汇合支线的 `renderPoints` 只负责可见线段，语义端点仍以完整 `points` 校验；自定义折叠实现应传入可见容器作为投影端点。形状轮廓与遮挡还需截图核验，矩形包围盒检查不能代替这一项。

connector：`id, relation, importance, points, arrow?, label?, labelAt?`，只画公共线段，不增加逻辑节点。将组成支线以 renderPoints 接到公共竖线，再由公共出口指向实际结果节点。不要用视觉汇合掩盖不同条件或不同目标。

## 动效与文档

motion.steps 显式选边，不自动把所有关系变成执行步骤。默认只允许 importance=primary 且 relation=flow 或 loop 的边参与；概念型通常省略 motion。一次步骤可有多个并行 edge ID，回路边之后可再次列出后续步骤。条件、组成、引用与辅助线保持静态。

文档从 groups/nodes 的 explanation 自动生成，按照分组嵌套与各数组中的顺序展示。不要另写一份同义正文。样例在文档中可折叠，在节点详情中完整显示。FAQ.answer 复用 explanation 结构，nodeIds 仅引用相关节点，不能生成不存在的链接。

## 构建与视觉验证的边界

构建器检查字段、唯一 ID、引用、层级环、数据类型和原文 JSON 语法。浏览器检查器验证包含边界、节点与文本重叠、说明与样例一致、交互状态和全屏。关系是否准确、材料是否漏读、布局是否好理解仍需人工审查与用户验收。
