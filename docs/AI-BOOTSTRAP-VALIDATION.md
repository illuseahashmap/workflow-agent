# 接手入口验收记录（2026-11-28）

## 验收对象

- 后端：`587c1bc7f7fe9e0dae356f3af5e8ffbe6dad1de4`。
- 前端：`1557c7892920f2b2bc65564904c178c6e078fefe`。
- 操作系统：Windows；JDK 25；Python 环境由 uv 按锁文件重新创建。
- 统一入口：`python scripts/test-local.py --suite all --p17`。

测试入口使用随机密码、随机 loopback 端口和独立 Docker 容器，Java 测试库与 Python 检查点库分离；部分集成测试另外使用 Testcontainers 创建自己的数据库。没有使用日常业务数据库或真实模型凭据。

## 已验证的初始化与隔离行为

- `scripts/check-release.py` 校验两个子模块的提交、索引指针与工作区一致。
- `docker compose --env-file .env.example config --quiet` 通过；基础镜像标签可查询。
- 后端 `scripts/local-postgres-init.sql` 在空库创建角色与数据库；更改角色密码后再次执行，密码哈希保持不变，数据库所有者不变。
- 入口的三个标准库回归测试覆盖：web 不建库、命令失败只清理本次容器、容器创建失败不清理已有服务；同时检查业务连接覆盖、迁移连接移除及关闭真实模型验收。
- Python 入口的 Ruff 检查和语法检查通过。

## 首轮发现与修正

初版入口将 WORKFLOW_MIGRATION_DB_* 固定到共享测试库，而部分 HTTP/Flowable 测试动态创建了自己的库。这导致 Flyway 和应用连接不同数据库，出现缺表。修正为移除继承的迁移连接，使 Flyway 跟随每个测试的有效 spring.datasource，并增加回归断言。

## 完整入口重跑结果

- Java `verify`：774 项，766 通过、8 条件跳过，0 失败、0 错误，耗时约 9 分 18 秒。
- 8 个跳过项：真实 P-17 原生/图、默认未开启的脚本化 P-17 图、两个本地真实 RAG、两个可选 specimen 专项、真实查询扩展。脚本化 P-17 图在后续 `--p17` 步骤单独开启，真实模型项仍不执行。
- Python Ruff 检查和 21 个文件的格式检查通过。
- Python pytest：103 项通过，包含独立 Java/Python 联合恢复与治理覆盖率门槛，耗时约 5 分 33 秒。
- P-17：原生/LangGraph × 旧/新证据契约，四组执行均通过，覆盖 28 个脚本化场景。
- 前端：冻结锁文件安装、格式、lint、类型、构建及包体积门槛通过；51 项单元测试和 23 项 Chromium E2E 通过。已有 9 条 Playwright 测试风格 lint 警告，0 错误。
- 统一入口最终退出码为 0；本次独立容器及匿名卷已由 finally 清理，未残留 workflow-test 容器。

重跑期间补充了 TCP 就绪探测、异常类型收窄和格式整理；这些入口改动随后通过标准库回归与 Ruff 检查，未改变测试选择与连接策略。

## 验证边界

此记录验证开发环境测试入口，不代表生产部署验收或真实模型质量评测。Compose 配置检查不等于完整 Compose 应用部署已实测。Linux/macOS 命令路径已在入口提供，但本轮完整运行环境是 Windows。条件跳过项不计为通过。
