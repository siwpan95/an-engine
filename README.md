# an-engine（alloy）

统一游戏引擎（原 allin_engine，2026-08-23 改名 alloy）。

- 引擎本体：lloy/（入口 rom alloy import GameEngine）
- 兼容 shim：llin_engine/（旧名导入自动重定向到 alloy，迁移完成后可删除）
- 架构：ECS + EventBus(emit/waterfall/serial) + 可逆装配内核 Context + 标准预设 preset + 世界事件日志 WorldLog（日志即事实源）
- 自省/审计/同步 CLI：python -m alloy dump-profile [--json]、python -m alloy dump-log <path>、python -m alloy sync <项目> --dry-run|--apply
- 测试：python -m alloy.test.run_all（369 项，无头环境 1 项 Tk 测试除外）

许可证见 alloy/LICENSE。
