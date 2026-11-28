# AI 接手：从克隆到首次运行

维护日期：2026-11-28。适用于本仓库锁定的前后端组合；这是一份开发环境指南。无需之前的聊天记录、个人磁盘目录、GitHub 登录、模型 Key 或 LangSmith 账号即可启动基础平台。私有仓库、镜像代理或真实 Provider 另按所在环境配置凭据。

## 1. 确认拿到完整代码

```sh
git clone --branch codex/integration-hardening --recurse-submodules https://github.com/illuseahashmap/workflow-agent.git
cd workflow-agent
git submodule update --init --recursive
git status --short
python scripts/check-release.py
```

Windows 可用 `py -3` 替代 `python`。如果正在接手指定分支，先 checkout 对应的**根仓库分支/提交**，再初始化子模块。不要用 `git submodule update --remote` 把后端和前端各自切到最新主分支：它们可能还没有一起验收。检查失败时核对清单与子模块指针，不要覆盖他人的未提交修改。

目录：根仓库负责组合部署；`workflow-agent-service` 是 Java 后端；`workflow-agent-web` 是 Vue 前端；Python 位于 `workflow-agent-service/agent-runtime-langgraph`。

## 2. 安装哪些环境

| 运行方式 | 必需环境 | 版本来源 |
| --- | --- | --- |
| 首次体验，推荐 Docker Compose | Git、已运行的 Docker Engine/Desktop（含 Compose v2）、Python 3.12+ 用于清单检查 | 镜像见 compose.yaml 和 deploy/*.Dockerfile |
| 在宿主机修改 Java / Vue | 上述环境，加 JDK 25、Node.js 24.12+、Corepack | Maven Wrapper 3.9.12；前端 packageManager 锁定 pnpm 11.8.0 |
| 启用 LangGraph Worker | Python 3.12–3.14、uv、独立 PostgreSQL 检查点库 | pyproject.toml / uv.lock；CI 使用 uv 0.12.6 |
| 运行浏览器测试 | 前端依赖及 Playwright Chromium | pnpm exec playwright install chromium |

用 `git --version`、`docker version`、`docker compose version`、`python --version` 检查基础工具；宿主机开发再检查 `java -version`、`node --version`、`corepack pnpm --version`。`JAVA_HOME` 必须指向 JDK 25。Maven 使用仓库 Wrapper，不要求另外安装 Maven；前端使用 `corepack pnpm install --frozen-lockfile`，Python 使用 `uv sync --frozen`，不全局安装一批未锁定的依赖。

Windows 的 Docker Desktop 使用 Linux containers；若提示 WSL unresponsive，先确认 `wsl --version`、`wsl --status`、`docker info` 能正常返回，再构建。不要在 Docker 尚未就绪时反复重装项目依赖。首次构建需要访问镜像仓库、Maven Central、npm 和 Python 包源；网络失败须单独报告，不能解释为应用测试失败。

安装方式：Git/Docker Desktop/JDK 25/Node.js 使用所在系统的软件包管理器或对应官方发行安装器，选择上表的版本；安装 JDK 后设置 JAVA_HOME 并将其 bin 加入 PATH，重新打开终端核对版本。uv 可用 `python -m pip install --user uv==0.12.6` 安装，再确认用户 Scripts/bin 已在 PATH。Node.js 发行包若未附带 Corepack，可用 `npm install --global corepack` 安装，随后使用 `corepack pnpm`，不另行安装不匹配的 pnpm。不需要 AI 从聊天里寻找某个人的 SDK 安装目录。

## 3. 首次启动：Docker Compose

从根目录操作。Linux/macOS 使用 `cp .env.example .env`；PowerShell 使用 `Copy-Item .env.example .env`。**仅在 .env 不存在时复制**。现有 .env、管理员密码和加密密钥必须保留。

根 `.env` 需要这些值：

| 配置 | 用途 |
| --- | --- |
| POSTGRES_PASSWORD | Compose 新数据库账号密码；改文件不会自动修改已有卷里的密码 |
| WORKFLOW_MASTER_KEY_BASE64 | 32 字节随机 AES 密钥的 Base64；更换会影响已保存凭据解密 |
| WORKFLOW_AUTH_TOKEN_SECRET | 独立随机登录签名密钥 |
| WORKFLOW_BOOTSTRAP_ADMIN_USERNAME | 初始管理员名，默认 admin |
| WORKFLOW_BOOTSTRAP_ADMIN_PASSWORD | 至少 12 字符的初始密码；启动不会重置已有用户密码 |

仓库样例为本机评估值。新环境应自行生成随机值、仅保存到本地 .env，不提交或贴进报告。Python 标准库 `secrets.token_bytes(32)` + `base64.b64encode` 可生成 AES 值，`secrets.token_urlsafe(32)` 可生成独立签名密钥/密码。不要拿实际 Provider Key 充当这些密钥。

```sh
docker compose config --quiet
docker compose up --build --detach --wait --wait-timeout 300
docker compose ps
```

前端 `http://localhost:5174`，后端健康检查 `http://localhost:8080/actuator/health`。浏览器使用 .env 的管理员登录。前端 `/api/...` 会去掉 `/api` 再代理到后端；直接请求 8080 时不带 `/api`。

现有 Compose 对宿主机发布 5174/8080，postgres/redis 仅在容器网络中使用。它采用 local profile，开放本地开发便利配置，不是生产部署模板。端口已占用时先识别占用者，再选择经核对的端口映射；不要杀掉不相关服务。当前没有承诺可直接运行的“一键安装全部 SDK”脚本。

```sh
docker compose logs --tail=100 backend
docker compose logs --tail=100 postgres redis
docker compose down
```

`down` 保留数据卷。`down -v` 会删除本地数据库，不能当成常规排障或升级步骤。镜像构建错误先核对具体镜像 tag、网络、磁盘和镜像源，不随意升级锁文件来绕过失败。

## 4. SQL 和初始化数据的唯一来源

| 内容 | 维护位置 / 执行方式 |
| --- | --- |
| Compose 数据库、账号 | postgres 镜像读取 POSTGRES_DB/USER/PASSWORD，在空卷首次初始化 |
| 外部/宿主机 PostgreSQL 建库 | 后端 scripts/local-postgres-init.sql；仅本地开发，由数据库管理员运行；重复执行不重置已有账号密码 |
| 平台表、租户、角色、权限、内置工具、运行时策略 | 后端 platform-migrations/src/main/resources/db/migration/platform/V*；由 Flyway 启动执行，当前统一至 V85 |
| Flowable 表 | local profile 的 flowable.database-schema-update=true；普通配置为 false，生产迁移另走部署流程 |
| 初始管理员及平台角色绑定 | PlatformAdminBootstrap；通过上述环境变量启用，不维护明文密码 INSERT |
| 向量扩展与表 | 后端 db/migration/vector 的 repeatable migration；需要安装 pgvector 的 PostgreSQL，不能直接在普通 postgres 镜像假定扩展存在 |
| Python 检查点表 | 独立检查点库中调用 initialize_checkpoint_store；不归 Java Flyway，不在 Worker 启动时自动建表 |
| P-17 / RAG 验收夹具 | 后端 docs/fixtures、测试类和 scripts/test-p17-*.ps1；只导入一次性测试库 |

不要手工逐个执行 V1–V85，也不要将测试库 dump 作为默认初始化数据。Flyway 管理执行顺序和校验和。已执行迁移不可编辑；新增表或必要种子数据必须增加唯一版本的迁移，并保证租户隔离、发布快照不可变和重复升级的行为可验证。

**已有数据库不是首次初始化。** 主分支曾使用另一组 V81/V82；升级前阅读 [分支历史升级说明](../workflow-agent-service/docs/architecture/branch-integration-upgrade-20261128.md)。严格区分正常 migrate 与一次性审计桥接，禁止盲目 repair、删除历史表或常开 outOfOrder。备份和维护窗口按说明执行。

## 5. 宿主机开发（需要改代码时）

Compose 默认不发布数据库端口，不能启动两个基础容器后直接假设宿主机可连 5432。准备自己已有的本地 PostgreSQL/Redis，或为开发 Compose 配置经过确认的 loopback 端口映射；避免和日常实例冲突。Java 数据库 URL 与数据库账号必须对应实际实例。

后端的完整独立启动步骤见 [后端本地运行指南](../workflow-agent-service/docs/operations/local-development.md)。复制后端 `.env.example` 到本地文件供 IDE 或启动器加载：**Java/Maven 不会自动读取 .env**。PowerShell 使用 `$env:KEY='value'`，bash 使用 `export KEY='value'`；设置文件中的每个必需配置，并使用 `SPRING_PROFILES_ACTIVE=local`。

```sh
cd workflow-agent-service
# Windows 使用 .\mvnw.cmd，其他平台使用 bash ./mvnw
bash ./mvnw -pl workflow-boot -am -DskipTests package
java -jar workflow-boot/target/workflow-boot-0.1.0-SNAPSHOT.jar
```

另开终端进入前端：

```sh
cd workflow-agent-web
corepack pnpm install --frozen-lockfile
corepack pnpm dev
```

默认代理后端 8080。如后端端口不同，在启动 Vite 的**进程环境**设置 `VITE_API_PROXY_TARGET`；目前 vite.config.ts 直接读取 process.env，不应只写 .env 就假定代理已改变。固定访问同一 hostname（localhost 或 127.0.0.1），避免 Cookie/CSRF 因主机名混用失效。

## 6. 可选：真实模型、RAG 与 LangGraph

基础启动无需真实模型凭据。先用页面配置 MOCK Provider 完成 Agent 定义、版本发布和运行；真实 Provider 的 API Key 经 Java 管理接口加密保存，不复制到前端、Python、SQL 种子或 Git。模型超时/额度不足不能通过关闭校验或无限重试解决。

关键词 RAG 不需要 Embedding Key。通过知识管理页面上传文档，等待摄取完成，创建并发布检索 Profile，绑定冻结索引，授予运行主体所需 scope，再发布绑定 Profile 的 AgentVersion。仅有文档不等于 Agent 已获授权。查询扩展默认 DISABLED，新版本可选择 RRF_V1；原版本不能原地修改。

向量 RAG 需要 pgvector、vector migration location，以及 WORKFLOW_KNOWLEDGE_EMBEDDING_* 的 Provider、地址、Key、模型、版本和维数。维数必须匹配生成向量；参照后端 application-vector.yml 和现有向量验收文档。默认 Compose 的普通 postgres 镜像不能替代 pgvector 部署。

LangGraph 是显式启用项，启动 Python 不会自动把所有业务切到图后端：

1. 用 `uv sync --project agent-runtime-langgraph --frozen` 安装锁定依赖。
2. 数据库管理员新建**独立**检查点库，并配置 WORKFLOW_LANGGRAPH_CHECKPOINT_DSN；不要指向 workflow_agent 业务库。迁移账号调用 `initialize_checkpoint_store` 一次。具体命令和权限见后端本地指南。
3. Java 配置 WORKFLOW_GRAPH_ENABLED=true、WORKFLOW_GRAPH_WORKER_TOKEN、WORKFLOW_GRAPH_ARTIFACT_DIGEST。Python 配置 GRAPH_GATEWAY_URL、GRAPH_WORKER_TOKEN、GRAPH_ARTIFACT_DIGEST、WORKFLOW_LANGGRAPH_CHECKPOINT_DSN。Token 与 artifact 指纹必须两端一致。
4. 本机 HTTP 联调需两端显式开启 loopback，URL 使用 127.0.0.1；容器服务名不属于 loopback。远程/容器间部署用受控 HTTPS，不把允许任意 HTTP 当作解决方案。
5. 管理员配置资源账户/绑定，新 AgentVersion 冻结 LANGGRAPH 与对应 artifact 后发布；已有版本仍保持 NATIVE 或其原指纹。
6. 后端目录运行 `uv run --project agent-runtime-langgraph python -m workflow_agent_runtime`。

当前 Compose 不包含 Python Worker，也不透传图宿主配置。使用此项前按 [图宿主配置](../workflow-agent-service/docs/operations/graph-dispatch-host.md) 和 [版本路由手册](../workflow-agent-service/docs/operations/version-runtime-and-call-reconciliation.md) 配齐宿主部署环境。开发本机指纹可基于锁定部署制品生成 SHA-256；发布后不能任意换指纹或重写已有检查点绑定。

## 7. 启动验收、排障与交接

启动不以“端口打开”为通过标准：

- 健康接口返回 status=UP；前端首页可打开。
- 浏览器登录成功，刷新后仍能读取当前用户；管理员可打开租户、流程定义和知识管理页面。
- 登录 API 先 GET `/auth/csrf` 保存 Cookie，再 POST `/auth/login` 携带 X-XSRF-TOKEN 和 JSON username/password；后续复用登录 Cookie。不要在日志中打印密码、Cookie 或令牌。
- 流程引擎表和 Flyway 迁移成功，无重复版本、缺表或 checksum mismatch。
- 若验证 Agent，明确记录 MOCK/脚本化还是实际 Provider，不用 MOCK 成功声称真实模型可靠。

常见问题：

| 现象 | 首先检查 |
| --- | --- |
| 8080 健康，但 API 404 | 是否启动旧 jar、路径是否多了 /api、前端代理是否指向旧实例 |
| 400 / scope-grants | principalId 不能为空；先选定运行主体 |
| 403 / CSRF | Cookie 与请求是否同 host、CSRF 是否刷新、是否误用生产 secure Cookie |
| 数据库密码错误 | .env 是否真的被加载；已有卷密码不会随 .env 改变 |
| Flyway V81/V82 冲突 | 按分支升级说明识别历史，不能 repair 掩盖 |
| 模型出站被拒绝 | 实际 DNS、协议和允许范围；不要关闭生产校验来适应代理 Fake-IP |
| 图不领取任务 | Java 图宿主、Token、artifact、版本后端、资源绑定、Python checkpoint schema |

### 新 AI 的直接测试入口

安装第 2 节的 Git、Docker、JDK 25、Node.js/Corepack、Python 和 uv，确认 Docker 已运行。**不需要先手工启动应用、不需要 .env、不需要创建业务库、也不需要真实模型 Key。** 在根目录运行：

```sh
python scripts/test-local.py --suite all --p17
```

Windows 可用 `py -3 scripts/test-local.py --suite all --p17`。入口先核对发布清单，使用 Docker 随机分配的 loopback 端口、新容器和随机密码，覆盖数据库测试环境变量，显式初始化独立 Python 检查点库，安装锁定 Python/前端依赖并运行验收；结束或失败后删除本次创建的容器和卷。不会连接日常业务数据库、加载 .env 或初始化真实 Provider。脚本主动关闭 WORKFLOW_RUN_LOCAL_RAG_ACCEPTANCE/WORKFLOW_RUN_LOCAL_RAG_AGENT_ACCEPTANCE，移除继承的 JAVA_TOOL_OPTIONS/JDK_JAVA_OPTIONS/_JAVA_OPTIONS/JAVA_OPTS/MAVEN_ARGS/MAVEN_OPTS；真实模型验收使用单独入口。

可按范围运行 `--suite backend`、`--suite graph`、`--suite web`；`--p17` 为原生/LangGraph × 旧/新证据契约的 28 个脚本化场景，不能搭配仅 web。graph 包含 Java/Python 跨语言回归，因此仍需要 JDK。首次下载依赖及完整验收可能需要几十分钟；不要把长时间无新增日志误判为卡死。Linux 缺少 Chromium 系统库时由环境管理员安装 Playwright 所需系统依赖后再运行，脚本不会自行提升权限安装系统包。

入口也会移除继承的 WORKFLOW_MIGRATION_DB_URL/USERNAME/PASSWORD，让 Flyway 跟随各测试的实际 spring.datasource；不能把迁移连接统一固定到一个测试库，因为部分集成测试会再创建自己的独立数据库。

退出码 0 表示所选命令全部成功；非 0 则查看最后失败步骤。Java 报告在后端各模块 `target/surefire-reports`，覆盖率在 `target/site/jacoco`，P-17 在 `workflow-boot/target/p17-runs` 和 `p17-graph-runs`，前端在 `test-results`。真实 Provider/独立专项的条件跳过不能计为通过。若脚本被强制结束，按本次输出的容器 ID 核对并清理，不按通配符删除其他容器。

底层回归入口仍保留：后端 `mvnw verify`；前端 `pnpm check`；Python `uv run pytest -q`。数据库和跨语言验收必须使用一次性数据库，按后端 scripts/test-langgraph-runtime.ps1 / CI 配置执行。P-17 是采购单场景，不是整个系统的质量分；参见 [本轮整合验收](../workflow-agent-service/docs/quality/branch-integration-20261128.md)。

交接时记录：三个仓库提交、采用的运行方式、端口、初始化/升级路径、已完成的验收、跳过项及原因。不要记录真实秘密。新增环境变量、依赖、初始化数据或迁移后，同时更新本指南、相应样例及验证记录。

本次统一入口的实测范围与结果见 [接手入口验收记录](AI-BOOTSTRAP-VALIDATION.md)。
