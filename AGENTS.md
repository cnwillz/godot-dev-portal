# Godot Dev Portal — AI 开发守则

本文件定义了 AI 助手在此项目中的开发规范、编码约定和工作方式。

## 总体原则

- **先读守则再动手** — 每次开始工作前先读 AGENTS.md 和 plan.md
- **迭代推进** — 按 plan.md 的步骤顺序做，不做超前实现
- **完成比完美重要** — MVP 功能的实现速度优先于过度设计
- **汇报式结束** — 每个步骤完成后总结做了什么、下一步是什么、有无阻塞

## 技术约定

### 后端 (Python/FastAPI)

- **框架**：FastAPI + SQLAlchemy 2.0 + Alembic
- **数据库**：SQLite（开发）/ PostgreSQL（生产预留）
- **异步**：路由和 service 层用 async/await
- **模板**：Jinja2（不需要前后端分离，MVP 阶段先用 SSR）
- **CSS 框架**：Tailwind CSS（CDN 引入，不配构建工具）
- **交互增强**：HTMX + Alpine.js 轻量结合

### 前端

- 服务端渲染为主，HTML 由 Jinja2 生成
- 表单交互用 HTMX：点击 → AJAX 请求 → 替换 DOM
- 复杂交互（实时日志、预览）用 Alpine.js 或 WebSocket
- CSS 在 `static/style.css` 或 Tailwind 内联
- **不引入 React/Vue** — MVP 阶段 SSR 够用

### Docker 集成

- 通过 `docker-py` (Docker SDK for Python) 管理容器
- 容器名称格式：`gd-portal-<project_id>-<purpose>`
- 预览容器端口动态分配（从 8000 开始找空闲端口）
- 测试容器运行后自动清理（`--rm` + 删除）
- 所有 Docker 交互写日志到 `data/logs/`

### 项目配置

- 环境变量在 `.env` 文件中
- 核心变量：
  - `DATABASE_URL` — 数据库连接（默认 sqlite:///./data/portal.db）
  - `GODOT_CI_IMAGE` — Docker 镜像名（默认 godot-ci:latest）
  - `VISION_API_KEY` — 视觉验证 API Key
  - `DATA_DIR` — 数据目录（默认 ./data）
- 数据库文件、日志、上传文件放 `data/`（已 .gitignore）

## 代码风格

### Python

- 类型注解：所有函数参数和返回值必须有类型提示
- import 顺序：标准库 → 第三方 → 本地
- 错误处理：业务逻辑用自定义异常，路由层用 try/except
- 日志：用 Python logging，不要 print

### 数据库

- 模型用 SQLAlchemy 2.0 声明式映射
- 关系用 `relationship()` + `ForeignKey`
- 时间戳字段用 `datetime.utcnow`（UTC 存储，前端转换）
- 模型文件放 `models.py`，路由在 `routers/` 下分文件

### 提交习惯

- 每个功能步骤完成后 git commit
- commit message 格式：`<步骤号>: <简要描述>`
- 示例：`step-1: init FastAPI project with SQLite models`

## 目录约定

```
backend/
├── main.py             # FastAPI app 入口 + 生命周期
├── config.py           # 配置类（pydantic-settings）
├── database.py         # engine + SessionLocal + Base
├── models.py           # 所有 ORM 模型
├── routers/            # API 路由
│   ├── __init__.py
│   ├── projects.py
│   ├── iterations.py
│   └── ...
├── services/           # 业务逻辑
│   ├── __init__.py
│   └── ...
├── templates/          # Jinja2 模板
│   └── ...
└── static/             # 静态文件
    ├── css/
    └── js/
scripts/                # 辅助脚本
└── seed.py
data/                   # 运行时数据（不提交 git）
├── portal.db
├── logs/
└── reports/
```

## 通信协议

### 实时日志（SSE）

测试容器的输出通过 Server-Sent Events 推送给前端：

```
GET /api/projects/{id}/test-logs
→ text/event-stream
event: log
data: {"line": "🧪 [unit] GdUnit4...", "timestamp": "..."}

event: complete
data: {"passed": true, "report_id": 1}
```

### WebSocket（预览）

预览容器通过 noVNC WebSocket 代理：

```
前端 Canvas → WebSocket → 后端代理 → noVNC → x11vnc → Xvfb → Godot
```

## 排错准则

- 每个新功能必须先跑通"快乐路径"再处理边界
- Docker 调用失败时检查：镜像是否存在、端口是否冲突、路径是否正确映射
- 数据库变更后用 `scripts/seed.py` 重置测试数据
- 模板渲染问题先检查变量是否传入 context
