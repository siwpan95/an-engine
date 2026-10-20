# Changelog

本项目所有值得注意的变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Changed

- **布局收口：双写镜像下线（2026-10-20）** —— 本仓长期存在两套被 git 跟踪的同一份代码：
  根侧 `core/ world/ systems/ …`（平铺布局，从工作区导入时的形态）与 `allin_engine/`
  （包目录布局，为发 PyPI 复制而来）。二者靠"人工双写"维持一致——最近一次双写是
  `e2f8996`（2026-10-20 12:57，3 个文件 × 2 侧）。逐文件比对（去掉 CRLF 差异）：
  可比 5,145 个文件中 5,139 个**逐字节相同**，仅 3 个漂移、3 个只在根侧
  （`CHANGELOG.md` / `SKILL.md` 本就属仓库根）。本次收口为**单一布局**：
  - 代码权威侧 = `allin_engine/`（`packages.find` 只收 `allin_engine*` 与 `alloy*`）；
  - 仓库根只保留 README / LICENSE / CHANGELOG / SKILL / pyproject / requirements /
    `alloy/`（兼容别名包）/ `web/`（TS 实验区）/ `.github/`；
  - 新增 `allin_engine/test/test_layout.py` 作机械门禁：根侧再出现镜像目录或旧入口、
    包内再夹带 README/pyproject 等根文件副本，测试当场失败 —— 防双写复活。

### Removed

- 根侧代码镜像（5,126 个文件，-186,203 行）：`core/ world/ systems/ render/ ai/ audio/
  fx/ utils/ trpg/ test/ media/` 与根 `__init__.py`、`__main__.py`、`cli.py`、`example_*.py`。
  与 `allin_engine/` 逐字节相同（去行尾差异），无内容损失；迁移前已做整仓 `git bundle` 备份。
- `allin_engine/` 内的根文件化石：`.github/`、`.gitignore`、`LICENSE`、`README.md`、
  `pyproject.toml`、`requirements.txt` —— 整仓复制时的残留，且已落后（根 README 302 行 vs
  包内副本 193 行；根 pyproject 3,616 字节 vs 包内 1,568 字节）。

### Added

- **系统读写声明与冲突告警（2026-10-20）**：把"隐式执行顺序"变成可检查的。
  - `System.reads` / `System.writes`（类属性，缺省空元组 = 不参与检查）。
  - `World.check_conflicts()`：返回所有「同相位 + 同 priority + 读写集合重叠」的系统对，
    带 `reason`（都写 / 一个写另一个读）与重叠组件名。**告警不是错误**——执行顺序不变。
  - `World.add_system(system, warn_conflicts=True)`：注册时即对**已注册系统**做一次检查，
    冲突发 `RuntimeWarning`；`warn_conflicts=False` 可静默。
  - 不声明读写集合的系统完全不受影响（原有 553 项测试全绿）；新增 10 项，套件 563。

- **系统相位 + 延迟事件（2026-10-20）**：解决"系统遍历时被自己触发的事件回头改容器"。
  - `System.phase` ∈ `pre` / `update` / `post`（缺省 `update`）。排序键改为
    **先相位、后 priority**——相位是硬顺序，priority 只在相位内部起作用。
    `add_system()` 对未知相位直接抛 `ValueError`（不拖到运行时才炸）。
  - `World.update()` 按相位推进，并在**每个相位边界**做两件事：
    `commands.flush()`（结构变更落地）与 `events.flush_deferred()`。
    于是 post 系统能看到 update 阶段的增删，而同相位内的系统仍看不到彼此
    未落地的增删（保持原先"遍历期间容器不变"的保证）。
  - `World.events`：每个 World 自带一个 `EventBus`。
  - `EventBus.emit_deferred()` / `flush_deferred()` / `pending_deferred` / `clear_deferred()`：
    延迟队列在 flush 期间新入队的事件留到下一轮，不会无限递归。
  - 兼容性：不使用 `phase` 的系统行为与以前完全一致（全部落在 `update` 相位，
    仅按 priority 排序）；原有 538 项测试全绿，新增 15 项后套件 553 项。

- **worldspec → MapGraph（2026-10-20）**：玩法层从此能直接吃 worldbuilder 的产物，
  且**不 import worldbuilder**（只读文件，守"复制优于共享"）。
  - `MapGraph.from_worldspec(dir)`：优先读 `graph.json`（含路网与过河点），
    没有则退回 `pois.json`（只有节点、没有边）。节点 `metadata` 带
    `x/z`（格）、`kind`、`elevation/biome/slope`、`tile_m`。
  - `MapGraph.edges` + `add_edge/edge_info/edge_length`：边权（路长）与折线；
    用嵌套 dict 存以便直接 JSON 序列化。`to_dict/from_dict` 同步扩展，旧载荷仍可读。
  - `route(start, goal)`：加权 Dijkstra（边权 = 路长），`weighted=False` 退 BFS；
    未知节点返回 `None` 不抛异常；`ignore_locks=False` 会绕开锁定节点。
  - `route_length()` / `nearest(x, z, kinds=...)` / `world_pos(id, meters=...)`。
  - 悬空边默认**跳过并记进 `load_report`**（玩法层不该因一条坏边整图报废），
    `strict=True` 时抛 `ValueError`（CI 用）。
  - 兼容性：`MapGraph` 新增 2 个带默认值的字段（`edges` / `load_report`），
    `MapGraph()`、`add_node`、`move_to` 等既有用法一字未改；套件 526 → 538 全绿。

- **ECS 存储 v2（P0-1 / P0-2，2026-10-20）**：`allin_engine/core/ecs.py`。
  - **组件倒排索引**：`World._comp_index`（组件类型 → {id: Entity}），查询先取"最小的那个桶"
    再逐个校验。20k 实体、1% 持有稀组件时，`get_entities_with_components` 从全表扫描的
    ~2.4ms 降到 ~0.02ms（测试断言 ≥3 倍且绝对 <20ms，实测两个量级）。
    索引由 `Entity.add/remove/clear_components` 与 `add_entity/remove_entity` 共同维护；
    **绕过这些入口直接改 `entity.components` 会让索引失准**（docstring 已写明）。
  - **实体代际**：`Entity.generation` / `Entity.is_alive`。实体被移除、被同名 eid 顶替、
    或被 `reset()` 时，代际 +1 且标记失效——旧句柄能识别"这个 id 已不是我认识的那个实体"。
  - **结构变更队列** `world.commands`：`create / remove_entity / add_component /
    remove_component` 先排队，`World.update()` 末尾统一落地（`flush_commands()` 可手动）。
    解决"边遍历 `world.each()` 边删实体"抛 `dictionary changed size during iteration`；
    `commands.create()` 返回**游离实体**，可先挂组件，flush 时随实体一起入世界并建索引。
  - 兼容性：`Entity` 新增 3 个槽位（`_world/_generation/_alive`），公共 API 与方法签名
    一个未改；原有 506 项测试全绿。测试 +20（`test_ecs_v2.py`），套件 526 项。

- **存档版本迁移（P0-3，2026-10-20）**：`allin_engine/core/world_serial.py` 增加 schema 头与迁移链。
  - `to_dict()` 输出 `{"schema": {"name": "allin-engine/world", "version": 1}}`；
  - 无 schema 头的历史存档按 **v0** 处理，由内置 `v0 -> v1` 补齐结构后反序列化；
  - `migrate(data, target, migrations, report)` 逐版本串联，**缺迁移路径直接报错**（不再静默丢字段）；
  - 版本高于引擎支持范围时抛 `SaveFormatError` **拒载**；
  - `register_migration(from_version)` 供下游扩展自己的 schema；
  - `world.load_report` 暴露 `migrated_from/steps/unknown_components/unknown_systems`，
    未知组件不再无声消失；测试 +13。
- **`skip_unless()` 跳过守卫 + 安装环境自测修正（2026-10-20）** ——
  字体按设计不随包分发（当前 wheel 约 3.4MB，字体单文件约 50MB，随包会再涨 27MB），但 `test_font.py` 里
  `test_discover_local_fonts_finds_bundled` 等 5 条断言的是"包内至少有随包字体"，
  于是在 `pip install allin-engine` 后跑 `allin-test` 会稳定报 5 个失败，
  让人误判成打包坏了。现给 runner 增加 `skip_unless(condition, reason)`，
  这 5 条在无随包字体的环境记为 **SKIP**，源码仓内仍照常真跑。
  验证：源码仓 506/506；干净 venv 装 wheel 后 501 通过 / 0 失败 / 5 跳过。

- **D20 界面壳并入（2026-10-20，siwpan/d20 仓确诊冗余后删除）**：
  D20 仓自 R2（2026-08-27）起已不含任何规则代码——`d20/` 只剩 5 个文件 77 行，全部是转发
  `allin_engine.trpg` 的薄 shim。经逐项比对确认冗余后，把其剩余内容整体迁入本仓，原仓删除：
  - `allin_engine/trpg/cli.py`：TRPG 命令行界面（控制台脚本 `allin-trpg`）；
  - `allin_engine/trpg/gui/`：tkinter 图形界面（控制台脚本 `allin-trpg-gui`）；
  - `allin_engine/trpg/samples/`：`sample_thief.py` + 黄金样例 `盗贼.txt`（package-data 随包分发）；
  - `allin_engine/trpg/docs/`：`content-expansion-plan.md`、`cordis-research.md`；
  - `web/trpg/`：TypeScript WebExtension 实验区（原 `d20/web/`，已排除 `node_modules`/`dist`）。
  - 刻意不迁 `mvp_builder.py` / `mvp_gui.py`：二者是转发到 `cli`/`gui` 的兼容壳，其目标
    「MVP 单文件版本」早已不存在，全量 grep 无任何外部仓引用。
  - 验收：`python -m allin_engine.trpg.samples.sample_thief` 与 `盗贼.txt` 的 12 个稳定
    关键字段逐字段一致；引擎套件 489/489 通过（未动内核）。

- **TRPG 规则内核并入（R2，自 D20）**：
  - `allin_engine/trpg/`：D20（D&D-GURPS 变体角色构建器，G:\local\D20）的 14 个子系统（属性/装备/优缺点/天赋/技术/种族/背景/专长/技能/骰子/衍生/法术位/休整/战斗宏/角色卡）+ 数据中枢 `data.py`（融合 D&D 三宝书与 GURPS Basic Set，单一事实来源）；
  - `TrpgContext`：allin_engine `Context` + `EventBus` 上的 D20 兼容适配层（`ctx.<service>` 属性代理、emit/waterfall/serial/parallel 分发、Service 插件基类）；事件骑宿主共享总线，构造即挂宿主 effect 栈（注册即回滚），dispose 逆序退订全部事件并清空服务；
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

### Changed

- **引擎改名：`alloy` → `allin_engine`（PyPI 项目名 `allin-engine`）**。`alloy` 不承载项目性质（既不体现"游戏引擎"，也不是合理的缩写），改回 `allin_engine`：
  - 包目录 `alloy/` → `allin_engine/`；全仓 **753 处引用、173 个文件**同步替换（整词匹配，零残留）；
  - `pyproject.toml` 同步：`name = "allin-engine"`、`packages.find.include = ["allin_engine*"]`、`package-data`、`console_scripts`（`allin-test = allin_engine.test.run_all:main`）；
  - 删除 2026-08-23 遗留的 `allin_engine/` 兼容 shim —— 它的作用是把 `allin_engine` 重定向到 `alloy`，方向已与本改名相反；
  - `project.urls` 修正：此前指向并不存在的 `https://github.com/quan/alloy`，改为实际仓库 `https://gitee.com/siwpan/an-engine`；
  - `description` 去掉内部路径 `D:\allin`；补 `classifiers` 与 `trpg` 关键词；
  - `cli.py` 的 `PRUNE_DIRS`：`alloy.egg-info` → `allin_engine.egg-info`。`sync` 的副本目录探测逻辑**无需修改**（本就同时兼容 `alloy` / `allin_engine` 两个名字）；
  - 验证：`allin_engine-1.0.0-py3-none-any.whl` 构建成功（顶层仅 `allin_engine/`），`twine check` PASSED；`import allin_engine` / `GameEngine` / `core` / `world` / `systems` / `trpg` 全部通过，旧名 `alloy` 已不可导入。
- **字体不再随包分发**：`fonts/` 移出 wheel —— 此前 27.3MB 里单个手写体就占 50.5MB（压缩后）。
  改为按需自备：`get_fonts_dir()` 新增「用户数据目录」兜底（`%APPDATA%\allin_engine\fonts`，
  不存在则自动创建），新增 `ALLIN_FONTS_DIR` 环境变量（与既有的 `ALLIN_FONT_PATH` 并存）；
  缺字体时自动降级到系统 CJK 字体。
  两个坑：① 仅删 `package-data` 无效 —— pyproject 模式下 setuptools 的 `include-package-data`
  默认为 True，会自动收录包目录下**被 git 跟踪**的文件（字体正在其中），须显式置 false；
  ② `*.egg-info/SOURCES.txt` 会缓存文件清单，导致重建继续沿用旧内容，须删 egg-info 并
  `--no-cache-dir`。最终 wheel **27.3MB → 340.9KB**。
- **5 个内联副本项目同步迁移**：`dwarf-scrolls/alloy`、`fish/tools/alloy`、
  `jotunnslayer/vendor/alloy`、`mahjong/alloy`、`mc-clone/alloy` → `allin_engine`
  （共 371 文件 / 1586 处引用），并删除各项目遗留的反向 shim、更新 `engine.patch.yaml`
  的 `engine` 字段。5 个项目导入验证均通过。

### Fixed

- `load_cjk_tk_font` 平台字体族未命中时，兜底 `tkfont.Font` 在根窗口销毁后创建导致 `Too early to use font: no default root window`；现于兜底前确保存在默认根窗口（无头 / 测试线程环境可用）。

## [1.0.0] - 2026-08-27

### Added

- 首个发行版：便携源码 zip（剔除 .venv/构建产物/输出物，依赖见 README）。
- 发布面：gitee [siwpan/an-engine](https://gitee.com/siwpan/an-engine) release `v1.0.0`（allin_engine 统一游戏引擎 v1.0.0）。