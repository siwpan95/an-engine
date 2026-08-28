# Changelog

本项目所有值得注意的变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added

- **TRPG 规则内核并入（R2，自 D20）**：
  - `alloy/trpg/`：D20（D&D-GURPS 变体角色构建器，G:\local\D20）的 14 个子系统（属性/装备/优缺点/天赋/技术/种族/背景/专长/技能/骰子/衍生/法术位/休整/战斗宏/角色卡）+ 数据中枢 `data.py`（融合 D&D 三宝书与 GURPS Basic Set，单一事实来源）；
  - `TrpgContext`：alloy `Context` + `EventBus` 上的 D20 兼容适配层（`ctx.<service>` 属性代理、emit/waterfall/serial/parallel 分发、Service 插件基类）；事件骑宿主共享总线，构造即挂宿主 effect 栈（注册即回滚），dispose 逆序退订全部事件并清空服务；
  - `preset_trpg(ctx)`：标准预设（幂等，已装且存活即复用），注册进 `STANDARD_PRESETS["trpg"]`；`Character(..., *, ctx=None)` 支持注入宿主 Context，多角色用 `ctx.fork(name)` + preset 独立装配、随作用域整体回收；
  - D20 自带的 mini-Cordis 与 YAML loader 不进入引擎（保留在 D20 仓库）；condition 子系统尚未接线（无状态字段、未进装配）暂不并入；
  - 测试 +105（规则行为契约 + 内核装配/总线/fork/回收契约），套件 484 项。
- **TRPG 骰子内核增强（R2 反向增强，moba_battle_platform 消费）**：
  - 纯函数（roll_d20/roll_d100/roll_d6/roll_3d6/roll_weapon_damage）新增可选 `rng` 参数（默认全局 random，行为不变；模拟器/测试可注入独立随机源）；
  - 新增通用 NdS 伤害骰 `roll_dice(count, size, rng=random)`（D&D 伤害骰；count<=0 返回 0、size<=0 收敛 1——与 moba_battle_platform 原语义一致，供其接入）；
  - 测试 +5，套件 489 项。
- **fork 双作用域语义**（Cordis fork / reusable 对齐，2026-08-27 深度审核后补）：
  - `Context.fork(name)`：命名子作用域，同名未销毁重复 fork 抛 `DuplicateScopeError`；销毁逆序回滚本层并自动从父上下文摘除（反复 fork/mount 不累积）；
  - `Context.fork_install(plugin, config, name=)`：插件 `outer(ctx)` 钩子按 name 在父作用域只执行一次（共享状态），`apply` 每次落独立 fork——同一插件多实例并存、逐实例独立回收；
  - `Context.scopes()` / `Context.name`：存活作用域清单与作用域名（健康面板/审计用）；
  - `GameEngine.mount_scoped(plugin, config, name=)` / `GameEngine.unmount(name)`：引擎级 fork 装配与整体卸载，WorldLog 记录 `plugin.mount` / `plugin.unmount` 事件；`shutdown()` 级联回收全部作用域挂载；
  - 依赖方向唯一：fork 可见引擎层服务（父链查找），反向不可见——实例服务经 fork 句柄访问。
- 测试 +10（fork 语义 7 + 引擎作用域挂载 3），套件 379 项。

### Fixed

- `load_cjk_tk_font` 平台字体族未命中时，兜底 `tkfont.Font` 在根窗口销毁后创建导致 `Too early to use font: no default root window`；现于兜底前确保存在默认根窗口（无头 / 测试线程环境可用）。

## [1.0.0] - 2026-08-27

### Added

- 首个发行版：便携源码 zip（剔除 .venv/构建产物/输出物，依赖见 README）。
- 发布面：gitee [siwpan/an-engine](https://gitee.com/siwpan/an-engine) release `v1.0.0`（alloy 统一游戏引擎 v1.0.0）。