# AI 接手入口

首次安装、配置、启动或排障，先读 [docs/AI-BOOTSTRAP.md](docs/AI-BOOTSTRAP.md)。以代码、锁文件和 `release-manifest.json` 为准，不依赖之前的聊天记录或某台电脑的绝对路径。

维护依赖版本、配置键、端口、迁移、初始化数据或启动命令时，同步更新该文档及相关 `.env.example`。平台表和基础数据由后端 Flyway 管理，Flowable 本地表由 local profile 初始化，Python 检查点使用独立数据库。不要把开发数据直接插入业务账本。

先检查工作区和现有服务；不要为启动项目重置已有数据库、密码、密钥、检查点或 Git 历史。已有库升级先读后端的分支升级说明。真实 Provider 调用与脚本化验收分别记录，跳过项不计为通过。
