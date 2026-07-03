# Godot Dev Portal — 游戏开发管理平台

## 项目概述

一个 Web 后台系统，用于管理 Godot 游戏项目的迭代开发全流程。
整合已有的 godot-docker-ci 容器化测试流水线，提供：
- 游戏实时预览（浏览器可玩）
- 迭代管理（创建、跟踪、完成）
- 每个迭代的实现过程记录
- 自动化验收报告（单元测试 + 截图 + 视觉验证 + 交互序列）
- 完整历史追溯

## 技术栈

| 层 | 技术 | 理由 |
|----|------|------|
| 后端 | Python + FastAPI | 异步、自动 API 文档、Python 生态 |
| 数据库 | SQLite (via SQLAlchemy) | 单机部署，零配置 |
| 前端 | Jinja2 + HTMX + Alpine.js | 服务端渲染，少写 JS，快 |
| 容器 | Docker SDK for Python | 管理 godot-docker-ci 容器 |
| 实时流 | noVNC WebSocket → 前端 Canvas | 游戏预览 |
| 认证 | 简单 Token / 无（开发阶段） | MVP 快速迭代 |
| CI | godot-docker-ci 镜像 | 已有的测试流水线 |

## 核心数据模型

```
Project
├── id, name, description, godot_scene, created_at
├── Iterations[]
│   ├── id, name, status(draft|active|done), created_at
│   ├── Tasks[]
│   │   ├── id, title, description, status(todo|doing|done)
│   │   └── notes, attachments
│   └── Reports[]
│       ├── id, type(unit|snap|vision|seq), passed, details
│       ├── screenshots[]
│       └── created_at
├── Preview
│   └── container_id, status, vnc_port, started_at
```

## 功能模块

### 1. 项目管理
- [ ] 列出/创建/编辑项目
- [ ] 每个项目绑定一个 Godot 项目路径和 godot-ci.json 配置

### 2. 迭代管理
- [ ] 创建迭代（包含多个 Task）
- [ ] 迭代状态流转：draft → active → done
- [ ] 每个 Task 可记录实现笔记、代码提交

### 3. 自动化验收
- [ ] 触发 godot-docker-ci 测试容器运行
- [ ] 流式输出测试日志到前端
- [ ] 存储测试报告（截图、JSON、HTML）
- [ ] 测试结果展示（单元通过率、截图对比、视觉评分）

### 4. 游戏预览
- [ ] 启动/停止游戏预览容器
- [ ] 通过 noVNC 在浏览器中嵌入式可玩游戏
- [ ] 预览状态指示（运行中/已停止）

### 5. 历史追溯
- [ ] 按迭代查看所有测试报告
- [ ] 对比不同迭代的截图
- [ ] 查看迭代期间的全部日志

## 目录结构

```
~/godot-dev-portal/
├── plan.md               # 本文件
├── AGENTS.md             # 开发守则
├── .gitignore
├── README.md
├── backend/
│   ├── main.py           # FastAPI 入口
│   ├── config.py         # 配置
│   ├── database.py       # SQLAlchemy 连接
│   ├── models.py         # ORM 模型
│   ├── routers/
│   │   ├── projects.py   # 项目接口
│   │   ├── iterations.py # 迭代接口
│   │   ├── reports.py    # 报告接口
│   │   └── preview.py    # 预览容器接口
│   ├── services/
│   │   ├── ci_runner.py  # 调用 godot-docker-ci
│   │   └── preview.py    # 管理预览容器
│   └── templates/        # Jinja2 模板
│       ├── base.html
│       ├── projects.html
│       ├── project.html
│       ├── iteration.html
│       └── preview.html
├── frontend/             # 静态资源（CSS/JS）
│   └── static/
│       ├── style.css
│       └── app.js
└── scripts/              # 辅助脚本
    └── seed.py           # 测试数据填充
```

## 实施计划（迭代一：MVP）

目标是跑通"创建项目 → 创建迭代 → 执行验收 → 查看报告"核心链路。

### 步骤 1 — 项目骨架
- [ ] FastAPI 项目初始化
- [ ] SQLite 数据库 + ORM 模型
- [ ] 基础 Jinja2 模板布局
- [ ] 项目 CRUD 页面

### 步骤 2 — 迭代管理
- [ ] 迭代 CRUD
- [ ] Task CRUD（在迭代内）
- [ ] 状态流转 UI

### 步骤 3 — 自动化验收集成
- [ ] 调用 Docker SDK 启动 godot-docker-ci 容器
- [ ] 实时日志流（SSE 或 WebSocket）
- [ ] 报告结果存入数据库
- [ ] 报告展示页面（截图、测试统计）

### 步骤 4 — 游戏预览
- [ ] 启动/停止 noVNC 容器
- [ ] 嵌入式 noVNC 预览 iframe
- [ ] 预览状态管理

### 步骤 5 — 历史与对比
- [ ] 历史迭代列表
- [ ] 截图对比（左右/叠加）
- [ ] 时间线视图

## 边界与约定

- 每个项目对应宿主机上一个 Godot 项目目录（包含 addons/ 和 .godot/）
- godot-docker-ci 镜像已构建好（`godot-ci:latest`）
- 视觉验证 API key 存在环境变量 `VISION_API_KEY`
- 预览容器映射端口动态分配（5900+N / 8080+N）
- 数据库 SQLite 文件放在 `data/` 目录（已 .gitignore）
