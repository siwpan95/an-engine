---
name: alloy-engine
description: Maintain and extend the alloy unified game engine (G:/games/alloy, formerly allin_engine). Use for engine changes, plugin/preset work, sync operations, or engine-related bug reports.
agent_created: true
---

# alloy 统一游戏引擎维护

## 概述
统一游戏引擎（ECS + EventBus(emit/waterfall/serial) + Context 可逆装配内核 + preset + WorldLog 事件日志 + sync/dump 审计 CLI）。原名 allin_engine，2026-08-23 改名；兼容 shim 在 G:\games\allin_engine\。

## 结构
- core/: ecs.py, event_bus.py, context.py（注册即回滚）, plugins.py（preset）, profiles.py, world_log.py（日志即事实源）, config_loader.py（YAML 子集）
- cli.py + __main__.py：dump-profile / dump-log / sync
- test/run_all.py：自定义测试运行器，新测试必须**显式注册**进 imports 和 all_tests 两处

## 常用命令
- 全量测试：cd G:\games && python -m alloy.test.run_all（369 项，基线 368 通过，唯一失败 = 无头 Tk test_load_cjk_tk_font_local_first）
- 装配自省：python -m alloy dump-profile [--json]
- 审计：python -m alloy dump-log <path>
- 副本同步：python -m alloy sync <项目> --dry-run|--apply --reference <旧版副本> --take-base <glob> [--subset] [--import-prefix ...]

## 关键约定
- Context.provide 重复注册抛错，覆盖需 replace=True；dispose 逆序回滚
- 事件分派模式（emit/waterfall/serial）是事件契约，同一事件只能一种模式
- 内联副本项目必须带 engine.patch.yaml（补丁即差异）；sync --reference 用旧版区分"过期/定制"
- 复制优于共享：项目内联引擎副本是有意设计
- 远端：gitee siwpan/an-engine（master）

## 已知陷阱
- 默认字体优先包内 baocanmou 手写体（BUNDLED_FONT_STEM），项目加字体不影响默认
- SaveLoadManager.load_with_log 读的是磁盘日志文件，内存追加后需 save_to 落盘
- 引擎文件写代码时避免用模板字符串直接内插 \n（历史教训：多次破坏字符串）
