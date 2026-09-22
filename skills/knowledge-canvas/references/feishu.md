# 飞书正文交付

目标是在文档正文直接缩放、平移和阅读节点详情。先读取当前环境的 lark-doc Skill 与本次操作所需参考，CLI 参数以已安装版本的帮助为准。

## 身份和范围

使用用户选定的 profile，并显式指定 --as user。公司与个人账号分别核验，不从域名猜测身份。没有用户本次分享授权时，不上传新业务资料、不改文档共享权限。使用正常认证和 Keychain 保护，不通过降级凭证存储解决问题。

## HTML 合同

单文件 HTML，UTF-8，head 包含：

```html
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="use-iframe" content="true">
<meta name="html-box-height-mode" content="auto">
<meta name="description" content="本画布的简短内容说明">
```

正文 auto 模式使用普通文档流，根页面不设固定高度或 overflow:hidden。操作画布业务容器默认 640px 高，宽度自适应；全屏时用应用容器实际全屏尺寸。不要把像素高度写进 meta。

当前已核验的 HTML5 块上限为 500KB。写入前读取当前 skill 参考并按 UTF-8 字节数检查。大型原始样例可能使画布超限，先保留本地完整文件，再与用户确认缩小内容范围或拆成多个可独立交互的正文块；不静默裁剪原文、不自动改为附件或外部托管。

## 精确更新

从目标目录运行，文件参数使用相对 @./ 路径：

```sh
lark-cli docs +fetch --doc "$CANVAS_DOC" --detail full --as user --profile "$CANVAS_PROFILE"
lark-cli docs +update --doc "$CANVAS_DOC" --command block_replace --block-id "$CANVAS_BLOCK" --doc-format xml --content '<html5-block path="@./canvas.html"/>' --as user --profile "$CANVAS_PROFILE"
lark-cli docs +fetch --doc "$CANVAS_DOC" --detail full --as user --profile "$CANVAS_PROFILE"
```

CANVAS_DOC、CANVAS_PROFILE、CANVAS_BLOCK 由本次读取或用户选择填入，不写死历史 token、账号或内部地址。不存在可替换的 HTML 块时，按用户指定锚点插入；新建文档先走 lark-doc 的创建流程。

| 字段 | 使用方式 |
|---|---|
| document_id / revision_id | 确认目标和当前版本，必要时防并发覆盖 |
| content 中的 block id | 仅定位目标块，替换后重新读取 |
| reference_map 中 HTML 的 path 或 data | 读取真实 HTML，不能只检查占位标签 |
| result、warnings、tips | success 才计成功，检查降级和部分成功 |
| 其他正文和资源字段 | 保留原样，不重写无关块 |
| 分享权限、owner 等管理字段 | 本流程不主动修改 |

逐轮回读，比较目标 HTML 与本地内容，核对其他块未受影响。认证或权限失败时停止外部写入并保留本地产物；结果不确定先读取现状，避免重试导致重复插入。

## 交互证据

保存成功只证明正文块持有 HTML。本地 iframe 测试只证明受测浏览器中的表现。需要用户或可访问的真实客户端确认正文交互、全屏尺寸及底部操作栏；没有现场证据时明确标记待确认。全屏权限由宿主与浏览器决定，不修改父页面权限、不用 CSS 在 iframe 内伪造真正全屏。

