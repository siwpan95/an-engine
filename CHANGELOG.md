# Changelog

本项目所有值得注意的变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added

- **fork 双作用域语义**（Cordis fork / reusable 对齐，2026-08-27 深度审核后补）：
  - `Context.fork(name)`：命名子作用域，同名未销毁重复 fork 抛 `DuplicateScopeError`；销毁逆序回滚本层并自动从父上下文摘除（反复 fork/mount 不累积）；
  - `Context.fork_install(plugin, config, name=)`：插件 `outer(ctx)` 钩子按 name 在父作用域只执行一次（共享状态），`apply` 每次落独立 fork——同一插件多实例并存、逐实例独立回收；
  - `Context.scopes()` / `Context.name`：存活作用域清单与作用域名（健康面板/审计用）；
  - `GameEngine.mount_scoped(plugin, config, name=)` / `GameEngine.unmount(name)`：引擎级 fork 装配与整体卸载，WorldLog 记录 `plugin.mount` / `plugin.unmount` 事件；`shutdown()` 级联回收全部作用域挂载；
  - 依赖方向唯一：fork 可见引擎层服务（父链查找），反向不可见——实例服务经 fork 句柄访问。
- 测试 +10（fork 语义 7 + 引擎作用域挂载 3），套件 379 项。

## [1.0.0] - 2026-08-27

### Added

- 首个发行版：便携源码 zip（剔除 .venv/构建产物/输出物，依赖见 README）。
- 发布面：gitee [siwpan/an-engine](https://gitee.com/siwpan/an-engine) release `v1.0.0`（alloy 统一游戏引擎 v1.0.0）。