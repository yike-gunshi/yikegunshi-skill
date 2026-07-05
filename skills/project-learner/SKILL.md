---
name: project-learner
description: 项目深度学习与架构分析工具。系统性地分析任意项目的技术架构、数据模型、核心业务流程和实现细节，产出结构化的知识文档和 AI 开发指导，持久化保存并跨会话维护。触发方式：用户说"学习项目"、"分析项目架构"、"了解项目"、"项目分析"、"/learn-project"或需要深入理解一个代码库时使用。
---

# Project Learner

系统性学习任意项目，产出可持久化的架构知识文档和 AI 开发指导。

## 知识库目录

所有产出文件统一存储在 `~/project-knowledge/{project-name}/`，按项目隔离。

## 工作流程

### Step 0: 初始化

1. 确定项目根目录（用户指定或当前目录）
2. 从目录名推导 `{project-name}`（用户可覆盖）
3. 创建知识目录: `~/project-knowledge/{project-name}/`
4. 检查是否已有 `META.md`：
   - **已存在** → 读取，展示上次分析概要，询问用户意图：
     - `全量更新` — 重新分析所有阶段
     - `增量更新` — 只更新有变更的部分（对比 git log / 文件修改时间）
     - `指定阶段` — 只重新分析某个阶段
   - **不存在** → 全新项目，执行全量分析

### Step 1: 项目全景扫描

用 Glob / Read / Bash 收集信息，产出到 `01_OVERVIEW.md`:

```markdown
# {project-name} 项目概览

## 基本信息
- 名称/版本/描述/License
- 基础模板/脚手架（如有）
- Git 状态: 分支 / 最近提交 / 活跃度

## 技术栈
| 类别 | 选型 | 版本 |
|------|------|------|
| 语言 | | |
| 框架 | | |
| 数据库 | | |
| ORM | | |
| 认证 | | |
| 支付/集成 | | |
| 样式/UI | | |
| 测试 | | |
| 部署 | | |

## 目录结构
(带职责注释的核心目录树，排除 node_modules/.git/dist 等)

## 环境变量清单
(从 .env.example / .env.development 提取，按类别分组)

## 常用命令
(从 package.json scripts / Makefile / 文档提取)
```

**操作方法:**
- 读取 `package.json` / `requirements.txt` / `go.mod` / `Cargo.toml` / `pyproject.toml` 识别技术栈
- 读取 README / CHANGELOG / DEVELOPMENT_STATUS 了解项目状态
- `git log --oneline -20` 了解近期活跃度
- `ls -la` + Glob 扫描目录结构

### Step 2: 数据层分析

产出到 `02_DATA_MODEL.md`:

```markdown
# 数据模型

## 表/集合清单
| 表名 | 用途 | 关键字段 | 关联关系 |
|------|------|---------|---------|

## ER 关系图
(Mermaid erDiagram)

## 数据访问层
### {Model名}.ts / .py
- `方法名(参数)` → 用途说明

## 重要约定
- 价格单位: 分/元/美分
- ID 生成策略: UUID / 自增 / snowflake
- 软删除 vs 硬删除
- 时间戳字段约定
```

**操作方法:**
- 搜索 schema / migration / model / entity 文件
- Grep `createTable|Schema|Model|Entity|@Entity|class.*Model` 定位定义
- 读取所有 model 文件，提取方法签名和注释

### Step 3: API 与后端架构

产出到 `03_BACKEND.md`:

```markdown
# 后端架构

## 分层架构图
(Mermaid flowchart: 路由层 → 服务层 → 数据层)

## API 端点清单
| 方法 | 路径 | 功能 | 认证要求 | 请求参数 | 响应格式 |
|------|------|------|---------|---------|---------|

## 认证与鉴权
- 认证方式 / Provider / Token 结构 / 权限模型

## 第三方集成
| 服务 | 用途 | 集成方式 | 配置项 |
|------|------|---------|-------|
```

**操作方法:**
- Glob `**/route.ts` / `**/routes/**` / `**/*controller*` / `**/*handler*`
- Grep `app.get|app.post|router.|@Get|@Post|export.*GET|export.*POST`
- 读取 auth / middleware 配置

### Step 4: 核心业务流程

产出到 `04_BUSINESS_FLOWS.md`:

```markdown
# 核心业务流程

## 流程 1: {名称}
### 触发条件
### 时序图 (Mermaid sequenceDiagram)
### 涉及文件
### 关键逻辑
### 边界情况与错误处理

## 流程 2: ...
```

**操作方法:**
- 从 API 清单中识别核心业务路径（注册/登录/下单/支付 等）
- 追踪 route → service → model 的完整调用链
- 重点关注：支付、认证、数据一致性 相关流程

### Step 5: 前端架构 (如适用)

产出到 `05_FRONTEND.md`:

```markdown
# 前端架构

## 路由结构
| 路径 | 页面 | 组件 | 数据获取方式 |
|------|------|------|------------|

## 组件架构
- 组织方式 / 组件分类 / 共享组件
- Server vs Client 组件划分策略 (如适用)

## 状态管理
- 全局状态方案 / 服务端状态 / 表单管理

## 国际化 (如适用)
- i18n 方案 / 语言 / 翻译文件位置
```

### Step 6: 产出 AI 开发指导

产出到 `06_AI_DEV_GUIDE.md`（最核心的交付物）:

```markdown
# AI 开发指导文档

> 本文档用作 AI 开发任务的 System Prompt 前缀，确保 AI 遵循项目规范。

## 速查卡
项目名 / 技术栈一行概览 / 核心目录 / 常用命令

## 编码规范
(从现有代码归纳：命名规范、导入顺序、错误处理模式、API 响应格式、类型定义风格)

## 新增功能模板
### 新增 API 端点
1. 在 `{path}` 创建 route 文件
2. 在 `{path}` 添加 service 方法
3. 在 `{path}` 添加 model 查询
4. ...

### 新增页面
1. ...

### 新增数据表
1. ...

## 关键约束清单
- [ ] 约束1 (如: 价格字段单位是"分")
- [ ] 约束2 (如: 订单号需要特定前缀)
- [ ] ...

## 模块依赖图
(Mermaid graph: 标注修改连锁影响)

## 常见陷阱
1. ...
```

### Step 7: 更新元数据

产出/更新 `META.md`:

```markdown
# {project-name} 知识库

## 状态
- 项目版本: x.y.z
- 最后分析时间: YYYY-MM-DD HH:mm
- 分析覆盖阶段: 1-6 全部 / 部分
- 项目根目录: /absolute/path

## 需求现状
(从 README / Issue / TODO / DEVELOPMENT_STATUS 提取的当前开发状态)

## 待办/进度
(项目当前的开发进度，未完成的功能，已知问题)

## 分析历史
| 日期 | 类型 | 范围 | 备注 |
|------|------|------|------|
| YYYY-MM-DD | 全量 | 阶段 1-6 | 初始分析 |
| YYYY-MM-DD | 增量 | 阶段 3 | API 变更 |
```

## 增量更新策略

当用户对已分析过的项目再次执行时:

1. 读取 `META.md` 获取上次分析时间和项目路径
2. 运行 `git log --since="{上次分析时间}" --oneline` 查看变更
3. 运行 `git diff --stat HEAD~{N}` 识别变更文件
4. 将变更文件映射到对应阶段:
   - schema/model 变更 → 重新执行 Step 2
   - API/route 变更 → 重新执行 Step 3
   - 业务逻辑变更 → 重新执行 Step 4
   - 前端变更 → 重新执行 Step 5
   - package.json / 配置变更 → 重新执行 Step 1
5. 所有变更的阶段完成后，重新生成 Step 6 (AI 开发指导)
6. 更新 `META.md` 追加分析历史

## 执行规则

- **基于源码**: 所有分析必须来自实际代码，禁止臆测
- **引用定位**: 提及具体代码时标注 `文件路径:行号`
- **图表优先**: 架构、关系、流程优先用 Mermaid 图表达
- **阶段确认**: 每个阶段完成后暂停，展示摘要，等用户确认后继续（用户可通过说"继续"或"全部执行"跳过确认）
- **最小惊讶**: 不修改项目源码，只读分析
- **幂等安全**: 重复执行同一阶段，覆盖对应文件而非追加

## 快速使用

```
# 全量分析当前目录的项目
用户: 学习项目

# 分析指定目录
用户: 学习项目 /path/to/project

# 增量更新
用户: 更新项目知识库

# 只分析特定阶段
用户: 分析项目的数据模型
用户: 分析项目的 API 架构

# 查看已有知识
用户: 查看项目知识库
```
