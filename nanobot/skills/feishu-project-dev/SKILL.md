---
name: feishu-project-dev
description: 飞书项目关联开发工作流。当用户提到"飞书"、"事项"、"需求"、"缺陷"、"story"、"issue"或要基于飞书事项进行开发时触发。支持：(1) 关联飞书事项进行开发 (2) 自动记录工时 (3) 生成规范的 commit 并关联事项 (4) 推进工作流节点 (5) 上传讨论文档到事项
---

# 飞书关联开发工作流

基于飞书项目事项进行关联开发的完整工作流，自动跟踪工时、生成规范 commit、推进节点流转。

## 工作流概览

```
1. 确定事项 → 2. 获取详情 → 3. 记录开始时间 → 4. 分析方案 → 5. 执行开发 → 6. 提交代码 → 7. 更新飞书
                                                                              ↓
                                                    ┌─────────────────────────────────────────┐
                                                    │ - 添加评论（关联 commit）               │
                                                    │ - 更新工时（自动计算）                 │
                                                    │ - 推进节点（可选）                     │
                                                    │ - 上传文档（用户决定）                 │
                                                    └─────────────────────────────────────────┘
```

## 工具依赖

### fp CLI 工具

本 skill 依赖 `fp` 命令行工具。

**安装方法：**

```bash
# Linux/macOS 一键安装（推荐）
curl -fsSL https://go-self-update.oss-cn-shenzhen.aliyuncs.com/fp/latest/install.sh| bash

# Windows (PowerShell)
iex (iwr -UseBasicParsing https://go-self-update.oss-cn-shenzhen.aliyuncs.com/fp/latest/install.ps1)
```

**更新工具：**

```bash
# 自动更新到最新版本
fp selfupdate
```

**验证安装：**

```bash
fp version
```

### 其他依赖

- **git**: 代码版本控制

## 阶段 1: 确定关联事项

### 用户提供事项时

```bash
# 按 ID 查询
fp workitem get <ID> --type <TYPE> --output json

# 按名称搜索
fp workitem get "<名称关键词>" --type <TYPE> --output json
```

### 需要搜索事项时

```bash
# 全文搜索
fp workitem search "<关键词>" --output json

# 列出最近事项
fp workitem list --type <TYPE> --output json
```

### 多个匹配时

返回候选列表让用户选择，格式：
```
找到多个匹配的事项：
1. #12345 - 用户登录功能优化
2. #12346 - 登录页面重构
请选择要关联的事项编号。
```

## 阶段 2: 获取事项详情并开始会话

确定事项后：

1. **获取完整详情**
```bash
fp workitem get <ID> --type <TYPE> --output json
fp workflow show <ID> --type <TYPE> --output json
```

2. **开始开发会话** (自动记录开始时间和当前节点)
```bash
fp session start <ID> --type <TYPE>
```

3. **输出事项摘要**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
飞书事项: #<ID> - <名称>
类型: <TYPE> | 状态: <当前节点>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
描述: <事项描述>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## 阶段 3: 分析方案

根据事项类型采用不同策略：

| 事项类型 | 分析重点 |
|---------|---------|
| story/需求 | 功能设计、技术方案、实现步骤 |
| issue/缺陷 | 问题定位、根因分析、修复方案 |
| task/任务 | 任务拆解、执行步骤 |

**输出格式**: 简洁的方案要点，不输出代码。

## 阶段 4: 执行开发

用户确认方案后开始实施：
- 使用 TodoWrite 跟踪开发任务
- 按方案逐步实现
- 完成后准备提交

## 阶段 5: 提交代码

### Commit 规范

格式: `<type>(<scope>): <subject> [#<事项ID>]`

**Type 类型:**
- `feat`: 新功能
- `fix`: 修复缺陷
- `refactor`: 重构
- `docs`: 文档
- `test`: 测试
- `chore`: 其他

**示例:**
```
feat(auth): 实现用户登录功能 [#12345]
fix(login): 修复密码验证逻辑错误 [#12346]
refactor(user): 重构用户模块结构 [#12347]
```

### 执行提交

```bash
git add <files>
git commit -m "<type>(<scope>): <subject> [#<WORKITEM_ID>]

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

## 阶段 6: 更新飞书事项

**⚠️ 重要：在执行任何修改操作前，必须先确认上下文！**

在执行以下任何操作前，先向用户确认：
```
即将对飞书事项进行以下操作：
- 事项 ID: #<ID>
- 事项名称: <名称>
- 操作类型: [添加评论/更新工时/推进节点]

请确认是否继续？(y/N)
```

只有在用户明确确认后，才执行后续操作。

### 6.1 添加评论（关联 commit）

**确认上下文后**，执行：

```bash
fp comment add <WORKITEM_ID> "<评论内容>" --type <TYPE>
```

评论模板:
```
开发完成，已提交代码。

commit: <commit_hash>
分支: <branch_name>
变更: <changed_files_summary>

<可选: 简要说明实现要点>
```

### 6.2 更新工时

**确认上下文后**，使用 session 命令自动计算并更新工时:
```bash
# 查看当前会话状态
fp session status

# 结束会话并更新工时
fp session end --update-workhour
```

或手动更新:
```bash
fp workhour update <WORKITEM_ID> "<节点名称>" --start "<开始时间>" --finish "<结束时间>" --type <TYPE>
```

### 6.3 推进节点/流转状态（可选）

**⚠️ 确认上下文后再执行！**

#### 步骤 1: 查看当前工作流状态

```bash
# 查看当前工作流（包含工作流类型、当前状态、可流转状态）
fp workflow show <WORKITEM_ID> --type <TYPE> --output json
```

返回的 JSON 包含：
- `flow_type`: 工作流类型（"node_flow" 节点流 或 "state_flow" 状态流）
- `nodes`: 所有节点/状态列表
- `connections`: 状态转换连接（仅状态流）
- 当前状态信息

#### 步骤 2: 分析可流转的状态

**对于状态流（issue 等）：**

从 `workflow show` 的输出中：
1. 查看当前状态（`current_state`）
2. 从 `connections` 中找出 `source_state_key` 等于当前状态的所有转换
3. 提取对应的 `target_state_key` 作为可流转的目标状态

**对于节点流（story、task 等）：**

从 `workflow show` 的输出中：
1. 查看当前节点
2. 查看可用的下一步节点列表
3. 根据节点的 `status` 字段判断节点状态（1=待处理，2=进行中，3=已完成）

#### 步骤 3: 向用户展示并确认

**必须向用户展示以下信息并获得确认：**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
工作流流转确认
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
事项: #<ID> - <名称>
类型: <TYPE> | 工作流类型: <节点流/状态流>

当前状态: <当前状态名称> (<状态KEY>)

可流转到:
  1. <状态名称1> (<状态KEY1>)
  2. <状态名称2> (<状态KEY2>)
  ...

建议流转到: <推荐的状态>
理由: <根据事项类型和开发阶段给出的理由>

是否确认流转？(y/N)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**推荐状态的选择逻辑：**

| 事项类型 | 当前阶段 | 推荐目标状态 |
|---------|---------|------------|
| story/需求 | 开发中 → | "开发完成"、"待测试"、"Testing" |
| issue/缺陷 | 分析中 → | "处理中"、"In Progress" |
| issue/缺陷 | 处理中 → | "已修复"、"待验证"、"In Testing" |
| task/任务 | 进行中 → | "已完成"、"完成"、"Done" |

**注意事项：**
- 状态流的状态名称可能包含中英文，如 "处理中（IN PROGRESS）"
- 需要使用状态的 KEY（如 "IN PROGRESS"）而非显示名称
- 如果用户选择的状态不在可流转列表中，需要提醒用户

#### 步骤 4: 执行流转

**用户确认后，执行流转：**

```bash
fp workflow finish <WORKITEM_ID> "<目标状态KEY>" --type <TYPE>
```

**注意**:
- 使用状态的 KEY（如 "IN PROGRESS"），不是显示名称
- 如果状态 KEY 包含空格，需要用引号包裹
- 节点名称支持模糊搜索，如果有多个匹配会返回候选列表

#### 步骤 5: 验证流转结果

流转后，再次查看状态确认：

```bash
fp workitem get <WORKITEM_ID> --type <TYPE> --output json
```

检查 `status` 字段是否已更新为目标状态。

#### 错误处理

如果流转失败，可能的原因：
1. **缺少必填字段**: 某些状态转换需要填写特定字段（如"问题根本原因分析"）
   - 提示用户：该状态转换需要填写必填字段，建议在飞书 Web 界面完成
2. **无权限**: 当前用户没有权限执行该转换
   - 提示用户：没有权限流转到该状态，请联系管理员
3. **不允许的转换**: 当前状态不能直接流转到目标状态
   - 提示用户：当前状态不能直接流转到目标状态，请查看可流转状态列表

### 6.4 上传文档（用户决定）

询问用户:
```
是否将本次讨论的方案文档上传到飞书事项？
- 是: 生成 markdown 并上传
- 否: 跳过
```

文档内容包括:
- 需求/问题分析
- 技术方案
- 实现要点
- 相关 commit

## 快速参考

**注意**: `-p/--project` 和 `-u/--user` 参数会被 CLI 自动缓存，首次使用后无需重复指定。

| 操作 | 命令 |
|-----|------|
| 搜索事项 | `fp workitem search "<关键词>" -t <TYPE>` |
| 获取详情 | `fp workitem get <ID> -t <TYPE>` |
| 列出事项 | `fp workitem list -t <TYPE>` |
| 按视图查看 | `fp workitem list -t <TYPE> --view "<视图名称>"` |
| 列出视图 | `fp view list -t <TYPE>` |
| 开始会话 | `fp session start <ID> -t <TYPE>` |
| 查看会话 | `fp session status` |
| 结束会话 | `fp session end --update-workhour` |
| 查看工作流 | `fp workflow show <ID> -t <TYPE>` |
| 流转状态 | `fp workflow finish <ID> "<状态KEY>" -t <TYPE>` |
| 添加评论 | `fp comment add <ID> "<内容>" -t <TYPE>` |
| 更新工时 | `fp workhour update <ID> "<节点>" --start "<时间>" --finish "<时间>" -t <TYPE>` |

## 工作流类型说明

| 工作流类型 | 说明 | 常见工作项类型 | 特点 |
|-----------|------|--------------|------|
| 节点流 (node_flow) | 基于节点的工作流 | story, task | 节点有状态（待处理/进行中/已完成） |
| 状态流 (state_flow) | 基于状态的工作流 | issue | 状态本身就是流程，通过 connections 定义转换规则 |
