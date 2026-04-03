# Commit 规范

## 格式

```
<type>(<scope>): <subject> [#<事项ID>]

<body>

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

## Type 类型

| Type | 说明 | 对应事项类型 |
|------|-----|-------------|
| `feat` | 新功能 | story |
| `fix` | 修复缺陷 | issue |
| `refactor` | 重构代码 | story/task |
| `perf` | 性能优化 | story/issue |
| `docs` | 文档变更 | task |
| `test` | 测试相关 | task |
| `chore` | 构建/工具 | task |
| `style` | 格式调整 | - |

## Scope 范围

根据项目模块命名，常见示例:
- `auth` - 认证模块
- `user` - 用户模块
- `api` - API 接口
- `ui` - 界面相关
- `db` - 数据库相关
- `config` - 配置相关

## Subject 标题

- 使用祈使句
- 首字母小写
- 不加句号
- 50 字符以内

## 事项 ID 格式

### bracket 格式 (默认)
```
feat(auth): 实现用户登录功能 [#12345]
```

### prefix 格式
```
feat(auth): 实现用户登录功能 PROJ-12345
```

## 完整示例

### 新功能
```
feat(auth): 实现 JWT 用户认证 [#12345]

- 添加 JWT token 生成和验证
- 实现登录/登出接口
- 添加 token 刷新机制

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

### 修复缺陷
```
fix(login): 修复密码验证时的空指针异常 [#12346]

问题原因: 未对空密码进行校验
解决方案: 添加空值检查

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

### 重构
```
refactor(user): 重构用户服务层架构 [#12347]

- 抽取公共接口
- 分离业务逻辑和数据访问
- 添加单元测试

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

## 自动推断 Type

根据事项类型自动推断默认 type:

| 事项类型 | 默认 Type |
|---------|----------|
| story/需求 | feat |
| issue/缺陷 | fix |
| task/任务 | chore |

可根据实际变更内容调整。
