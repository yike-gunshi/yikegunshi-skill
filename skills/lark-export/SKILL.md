---
name: lark-export
description: Mirror a Feishu/Lark wiki subtree or a single Feishu doc to local Markdown, with images and attachments downloaded locally. Use whenever the user wants Feishu content available offline, in the repo, or greppable — 导出飞书文档, 同步知识库到本地, 把 wiki 拉下来, 刷新本地镜像, 备份那篇文档 — even when they never say "export" or "mirror", and even when they only paste a Feishu URL and say they want the content locally. First pull and re-sync are the same command, so updating an existing mirror also goes here. Not for reading, quoting, or summarizing one Feishu doc inside the conversation (use the feishu MCP tools directly — no local mirror needed), and not for writing or publishing back to Feishu (that goes to lark-cli docs +create/+update).
---

# lark-export — Feishu/Lark KB → local Markdown

Mirror a Feishu/Lark wiki or document to local Markdown, with images and attachments downloaded locally. First pull and update use the **same** command — re-running overwrites in place, which is safe when the local copy is treated as a read-only mirror (not hand-edited).

## Dependency

This skill drives a patched build of **`feishu-cli`** (the [larksuite/cli](https://github.com/larksuite/cli) tool, patched so `doc export` / `wiki export` download embedded images and attachments locally instead of leaving `feishu://media/...` references) plus a batch wrapper `feishu_cli_batch_export.py` that walks a wiki tree.

### Load the environment (do this first)

Three things must be set: `FEISHU_EXPORT_HOME` (the toolchain dir containing `bin/feishu-cli`, `runtime/feishu-cli`, `scripts/`), `FEISHU_APP_ID`, and `FEISHU_APP_SECRET`.

Do not go hunting for these by hand every time — the bundled script finds them:

```bash
python3 scripts/feishu_env.py --check      # report what was found, secret stays masked
eval "$(python3 scripts/feishu_env.py)"    # load them into the current shell
```

It locates the toolchain by looking for a directory containing `bin/feishu-cli`, and reads the app credentials at call time from the `feishu` MCP server entry in the nearest `.mcp.json` (searching upward from cwd, then `$HOME`). Pass `--config` / `--export-home` to override either.

Credentials are deliberately not stored in this skill — it is symlinked, packaged, and pushed to GitHub. Reading them from the MCP config at call time keeps them out of the repo. If `--check` reports a missing toolchain, build it (step 1); if it reports a missing config, set the two variables by hand.

## Sync model (read first)

- **First pull and update are the same command.** Run the batch script with the same `--out <dir>`; it re-exports every doc, overwriting local files. That is the update/sync behavior.
- `--skip-existing` flips it to "only add new docs, never touch existing files".
- Limitation (simple full-overwrite mode): if a doc is renamed or deleted upstream, its old local file is left behind as an orphan. No prune step yet.

## Choosing the output directory

If the user does not name an output directory, recommend one based on the current project structure instead of asking blindly: scan for a topically-matching existing home (match on the wiki's title/topic), propose that path or a clearly-labeled mirror subdir under it, and confirm before pulling. Never invent a fixed default silently.

## Workflow

### 1. Ensure the CLI binary exists

If `$FEISHU_EXPORT_HOME/bin/feishu-cli` is missing, build it (requires Go):

```bash
cd "$FEISHU_EXPORT_HOME" && ./scripts/build_feishu_cli.sh
```

### 2. Ensure a valid User Token

Read `~/.feishu-cli/token.json`. The token must have a **future** `expires_at` and include these scopes:

- `offline_access`
- `docs:document.media:download`
- `docs:document:export`
- `drive:drive:readonly`
- `drive:export:readonly`

If missing or expired, re-run OAuth login. This opens a browser and needs a human — it cannot run unattended:

```bash
"$FEISHU_EXPORT_HOME/bin/feishu-cli" auth login --no-manual \
  --scopes 'offline_access docs:document.media:download docs:document:export drive:drive:readonly drive:export:readonly auth:user.id:read'
```

App Token reads wiki/doc structure; User Token downloads images and runs `export-file`.

### 3. Get the node token from the URL

- Wiki URL `https://<host>/wiki/<node_token>` → `<node_token>` is the `--root-node`.
- Single doc URL `https://<host>/docx/<document_id>` → not a wiki node; use the single-doc command in step 5.

### 4. Pull / update a whole wiki subtree

Same command for first pull and every later update.

```bash
python3 "$FEISHU_EXPORT_HOME/scripts/feishu_cli_batch_export.py" \
  --root-node <root_node_token> \
  --out <output_dir> \
  --cli "$FEISHU_EXPORT_HOME/bin/feishu-cli" \
  --cli-repo "$FEISHU_EXPORT_HOME/runtime/feishu-cli"
```

Batch script arguments: `--root-node` (required), `--out` (required), `--cli` (required), `--cli-repo` (required), `--user-token` (optional; defaults to `~/.feishu-cli/token.json`), `--skip-existing` (optional), `--wiki-base-url` (optional, default `https://my.feishu.cn/wiki`).

### 5. Export a single document

```bash
"$FEISHU_EXPORT_HOME/bin/feishu-cli" doc export <document_id> \
  -o <target_dir>/<title>.md \
  --download-images \
  --assets-dir <target_dir>/<title>.assets \
  --front-matter \
  --user-access-token "$(python3 -c "import json,pathlib;print(json.loads(pathlib.Path.home().joinpath('.feishu-cli/token.json').read_text())['access_token'])")"
```

## Output layout

Under the `--out <dir>` you pass:

```text
<out>/docs/<root title>.md
<out>/docs/<root title>.assets/
<out>/docs/<child title>__<node_token>/<child title>.md
<out>/docs/<child title>__<node_token>/<child title>.assets/
<out>/reports/tree.json          # full node tree + per-node manifest
<out>/reports/export-report.json # item count + duration
```

- Parent nodes become directories named `<title>__<node_token>`; leaf docx become `<title>.md` + `<title>.assets/`.
- `file` nodes download the original attachment (extension preserved) plus a small `.md` stub.
- `bitable` (多维表格) nodes export to `.xlsx` plus a `.md` stub.

## Verify

- `<out>/docs/` contains the expected `.md` files.
- `.assets/` exists for docs with images; image references point to local files, not `feishu://media/...`.
- Frontmatter contains `source_url`.
- `<out>/reports/tree.json` and `export-report.json` were written; `items` count is non-zero.

## Common failures

- `dial tcp: lookup open.feishu.cn: no such host` — network blocked; re-run with network access.
- `Authentication token expired` / images stay as `feishu://media/...` — user token missing, expired, or lacking export/media scopes; re-run OAuth login.
- `code=1069902, msg=no permission` — user token lacks export scopes, or app/user authorization is incomplete.
- Browser says `redirect_uri 请求不合法` — the Feishu app is missing `http://127.0.0.1:9768/callback` in its redirect URI allowlist.
