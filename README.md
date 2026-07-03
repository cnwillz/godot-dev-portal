# Godot Dev Portal

Web 后台管理 Godot 游戏项目的迭代开发全流程。
整合 godot-docker-ci 容器化测试流水线，实现从"创建迭代 → 实现 → 验收 → 预览"的闭环。

## 功能

- 项目管理（创建/编辑/列表）
- 迭代管理（Task 拆分、状态流转）
- 自动化验收（一键触发 godot-docker-ci 全链路测试）
- 实时测试日志流
- 游戏预览（浏览器内 noVNC 可玩）
- 历史追溯与截图对比

## 快速开始

```bash
# 1. 克隆
git clone <repo-url>
cd godot-dev-portal

# 2. 安装
cd backend
pip install -r requirements.txt

# 3. 初始化数据库
python -c "from database import init_db; init_db()"

# 4. 启动
uvicorn main:app --reload --port 8000
```

## 目录结构

详见 `plan.md` 和 `AGENTS.md`。

## 依赖

- Python 3.11+
- Docker（需要 `godot-ci:latest` 镜像已构建）
- 宿主机需有 Godot 项目目录（含 addons/）
