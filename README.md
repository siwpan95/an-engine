# allin-engine — 统一游戏引擎

> 仓库：<https://gitee.com/siwpan/an-engine> ｜ 许可：MIT（见 [LICENSE](LICENSE)）
> 注：文中 <PATH> 为路径占位符，请替换为你本机实际的目录 / 可执行文件路径。

[![PyPI](https://img.shields.io/pypi/v/allin-engine)](https://pypi.org/project/allin-engine/)
[![Python](https://img.shields.io/pypi/pyversions/allin-engine)](https://pypi.org/project/allin-engine/)
[![License](https://img.shields.io/pypi/l/allin-engine)](https://pypi.org/project/allin-engine/)

**PyPI**：<https://pypi.org/project/allin-engine/> ｜ **发行名 `allin-engine` / 导入名 `allin_engine`**
（旧名 `alloy` 仍作为兼容别名包随包分发，见下文「安装」）。

从 <PATH> 下 100+ 个项目中提炼的通用 Python 游戏引擎（独立仓 siwpan/an-engine，本地 <PATH>），融合 ECS 架构、事件总线、世界模型、卡牌战斗、AI 叙事、音频合成等能力。

## 架构分层

单一布局：**代码全部在 `allin_engine/` 包内**。
2026-10-20 收口前，本仓曾把整个仓库根复制一份到 `allin_engine/`（为发 PyPI），
之后靠"双写"维持两份一致；现已下线镜像，仓库根只保留发行与治理文件
（README / LICENSE / CHANGELOG / SKILL / pyproject / `alloy` 兼容包 / `web` 实验区）。
`test_layout.py` 是这条决定的机械门禁。

```
allin_engine/core/      ECS + EventBus + Config + FixedTimestepLoop  ← 所有项目必用，零硬依赖
allin_engine/world/     世界模型 (状态/地图/物品/角色)      ← 游戏数据层，可序列化
allin_engine/systems/   游戏系统 (战斗/谜题/背包/存档/Mod)   ← 游戏逻辑层
allin_engine/render/    渲染 (终端/GUI/动画/公式引擎)       ← 表现层
allin_engine/audio/     音频 (合成/音乐/音效)              ← 依赖 numpy/scipy
allin_engine/fx/        粒子特效                          ← 依赖 numpy
allin_engine/ai/        智能 (叙事/对话/AI生成)            ← 可选 requests/ollama
allin_engine/ai/decision/ 决策范式 (状态机/行为树/决策树/差分引擎/ECS脑) ← 零依赖
allin_engine/media/     媒体子系统 (公式引擎/效果原语/CA 规则引擎)  ← numpy 可选 asteval（J2 S2/S3 并入）
allin_engine/trpg/      TRPG 规则内核 (自 D20 并入: D&D-GURPS 角色构建)  ← 零依赖
allin_engine/test/      测试工具 (自定义框架)              ← 零依赖
allin_engine/utils/     通用工具 (JSON/日志/字体/文本)      ← 零依赖
allin_engine/example_*.py  可运行示例（quickstart / decision_ai / local_font）
alloy/                  兼容别名包（旧导入名，随包分发）
```

## 引擎整合声明（J2 · 2026-08-25）

本仓是仓库内**唯一综合引擎**。引擎类关系：

- **pywallpaper**（壁纸应用）：其能力层（公式引擎/效果原语/4973 配方）已并入 media/，pywallpaper/engine 为内联副本（engine.patch.yaml 记录）；
- **cellular_automaton**（CA 壁纸应用）：其 CA 规则引擎（141 规则）已并入 media/ca/，cellular_automaton/core+ rules 为内联副本（engine.patch.yaml 记录）；
- **bloodmusic**（音频合成，独立仓）：**外部库**，与本仓 audio/ 是"提取独立化"关系（audio/synth.py 提取自 bloodmusic/core/，audio/music_gen.py 提取自 bloodmusic/music/），不并入、不互相版本锁定，各自独立更新。

## 安装

**方式一 · 从 PyPI 安装（推荐，用库）**

```bash
# 核心（零硬依赖：ECS + EventBus + World + Systems）
pip install allin-engine

# 渲染 + 音频增强
pip install "allin-engine[render,audio]"

# 全部可选功能
pip install "allin-engine[all]"
```

装完校验（注意导入名是下划线，发行名是连字符）：

```bash
python -c "import allin_engine; print(allin_engine.__version__)"
allin-test            # 随包安装的测试入口
```

**方式二 · 源码 editable 安装（改引擎 / 开发）**

```bash
# 核心（零依赖，ECS + EventBus + World + Systems）
pip install -e .

# 渲染 + 音频
pip install -e ".[render,audio]"

# 全部功能
pip install -e ".[all]"
```

> 兼容别名：`alloy` 包随 `allin-engine` 一同分发，旧代码 `import alloy.trpg...` 无需改动。

## 快速开始

```python
from allin_engine import GameEngine

# 一键装配
engine = GameEngine()
engine.add_core()       # ECS + EventBus
engine.add_world()      # GameState
engine.add_systems()    # Inventory + Puzzles + SaveLoad
engine.add_combat()     # 卡牌战斗
engine.add_audio()      # 音频系统

# 直接使用
world = engine.world
state = engine.state
inventory = engine.get("inventory")
```

```python
# 或按需导入
from allin_engine.core import World, Entity, Component, System, EventBus
from allin_engine.world import PlayerState, Room, Item, MapData, MapGraph
from allin_engine.systems import Inventory, PuzzleSystem, CommandParser
from allin_engine.systems.combat import CombatEngine, Card, CardDeck, Enemy
```

TRPG 角色构建（D20 规则内核，零依赖）：
```python
from allin_engine.trpg import Character, preset_trpg
from allin_engine.core import Context

c = Character()
c.set_attribute("力量", 16)
c.purchase_skill("近战攻击", 12)
print(c.show_sheet())

# 挂入引擎 Context（preset 风格，与其它预设共存）
ctx = Context()
preset_trpg(ctx)
c2 = Character(ctx=ctx)
```

运行示例：
```bash
cd <PATH> && python allin_engine/example_quickstart.py
cd <PATH> && python allin_engine/example_decision_ai.py
```

运行测试（484 个）：
```bash
cd <PATH> && python -m allin_engine.test.run_all
```

## 决策 / 行为范式（状态机 · 行为树 · 决策树 · 差分引擎）

`allin_engine.ai.decision` 集成了源自 zhuangtaiji 项目的四种计算/决策范式，
覆盖游戏 AI 与状态管理的核心需求，并与本引擎的 ECS 世界循环、事件总线深度打通：

| 范式 | 适用场景 | 关键 API |
|------|----------|----------|
| 状态机 FSM / HSM | 明确的状态 + 事件转移；层次状态机支持嵌套子状态/历史/内部转移 | `GenericStateMachine` / `HierarchicalStateMachine` / `create_state_machine` |
| 行为树 BT | 每帧重新评估的响应式 AI 行为编排（根驱动 tick） | `BehaviorTree` / `Blackboard` / `build_behavior_tree` |
| 决策树 DT | 基于特征空间的一次性路由决策 | `DecisionTree` / `DecisionResult` / `build_decision_tree` |
| 差分引擎 | 巴贝奇有限差分（加法递推）+ 状态差量/响应式脏检查 | `FiniteDifference` / `StateDiff` / `ReactiveTracker` |

**接入 ECS 世界循环**（让 NPC 拥有可驱动的「大脑」）：

```python
from allin_engine import GameEngine, BrainComponent, BlackboardComponent
from allin_engine.ai.decision import build_brain_from_spec, default_brains_config

engine = GameEngine()
engine.add_core().add_ai_brain()          # 注册 BrainSystem 到世界主循环
cfg = default_brains_config()

npc = engine.world.create_entity("goblin")
npc.add(BlackboardComponent({"fault": False, "load": 30}))   # 实体级黑板
npc.add(BrainComponent(
    tree=build_brain_from_spec(cfg["behavior_trees"]["BT_SelfHeal"]),
    name="goblin_ai",
))
engine.world.update(0.016)   # BrainSystem 自动 tick 行为树，结果写回实体黑板
```

**固定时间步长主循环**（游戏循环架构最佳实践，参考 Gaffer "Fix Your Timestep"）：

```python
engine = GameEngine()
engine.add_core()             # 内部创建 self.loop = FixedTimestepLoop
engine.advance(0.05)         # 按 1/60 固定步长切分多次 world.update，钳制单帧时间
```

更完整的示例见 `example_decision_ai.py`。

## 核心模块

| 模块 | 说明 | 行数 |
|------|------|------|
| `core/ecs.py` | Entity-Component-System：自增ID + 链式调用 + 类型安全；**组件倒排索引**（查询走最小桶）、**实体代际**（旧句柄可识别）、**结构变更队列** `world.commands` | 648 |
| `core/event_bus.py` | 松耦合事件总线，递归保护 + 一次性监听 + 装饰器模式 | 355 |
| `world/game_state.py` | 玩家状态 + 游戏状态 + 章节枚举 + to_dict/from_dict | 377 |
| `systems/combat/` | 回合制卡牌战斗：CombatState + 12种Buff + 敌人意图系统 | 1347 |
| `ai/generator.py` | Ollama/DeepSeek 双后端 + 中文模板降级 | 542 |
| `render/formula_engine.py` | 安全数学公式求值 (asteval优先，纯Python回退) | 363 |
| `fx/particle.py` | 高性能粒子系统：Particle + Emitter + ForceField | 949 |
| `core/game_loop.py` | 固定步长主循环 FixedTimestepLoop（累加器 + 单帧钳制防死亡螺旋 + 插值 alpha） | 新增 |
| `ai/decision/state_machine.py` | 通用/层次状态机 FSM/HSM：嵌套子状态/历史/内部转移 `#` | 移植 |
| `ai/decision/behavior_tree.py` | 行为树 BT：组合/装饰/条件/动作 + Blackboard + 声明式构造 | 移植 |
| `ai/decision/decision_tree.py` | 规则型决策树 DT：Condition/Switch/Action 路由 | 移植 |
| `ai/decision/difference_engine.py` | 差分引擎：有限差分递推 + StateDiff + ReactiveTracker 响应式 | 移植 |
| `ai/decision/brain.py` | ECS 粘合层：BlackboardComponent / BrainComponent / BrainSystem | 新增 |
| `trpg/context.py` | TrpgContext 适配层：allin_engine Context+EventBus 上的 D20 兼容视图（属性代理/事件分发/Service 基类） | 并入 |
| `trpg/character.py` | Character 公共门面：14 服务委托 + ctx.state 状态代理 + preset 装配 | 并入 |
| `trpg/data.py` | 规则数据中枢（D&D 三宝书 + GURPS Basic Set 融合，单一事实来源） | 并入 |

## TRPG 规则内核（D20 并入 · R2）

`allin_engine.trpg` 是 D20（D&D-GURPS 变体角色构建器，siwpan 项目，原 <PATH>）规则内核的
engine 化版本：14 个子系统（属性/装备/优缺点/天赋/技术/种族/背景/专长/技能/骰子/衍生/
法术位/休整/战斗宏/角色卡）挂到 allin_engine 的可逆装配内核上，事件骑共享 EventBus，
`preset_trpg(ctx)` 与其它标准预设同一套装配协议。

- **并入口径**：D20 自带的 mini-Cordis 容器与 YAML loader 不进入引擎（历史形态，随 D20 仓一并下线）；
  allin_engine 侧由 `TrpgContext` 适配层 + 代码预设替代；`condition` 子系统尚未接线（无状态字段、
  未进装配），暂不并入。
- **多角色**：一个宿主 Context 一个内核；每角色独立装配用 `ctx.fork(name)` + preset，
  fork 销毁即整体回收。
- **借鉴记账**：规则数据与 14 服务源码自 D20 迁移，行为契约由测试钉住（+105 项，
  与 D20 原测试期望逐一对齐）；D20 后续经此内核反向重构。

### 2026-10-20：D20 界面壳并入，siwpan/d20 仓确诊冗余后删除

R2 之后 D20 仓只剩「薄 shim（`d20/` 5 文件 77 行，全部转发 `allin_engine.trpg`）+ 界面壳」，
规则代码为零。界面壳已整体迁入本仓，原仓（Gitee `siwpan/d20` + 本地 `G:\repos\d20`）删除：

| 原 D20 路径 | 本仓落点 |
|---|---|
| `cli.py` | `allin_engine/trpg/cli.py`（控制台脚本 `allin-trpg`） |
| `gui/` | `allin_engine/trpg/gui/`（控制台脚本 `allin-trpg-gui`） |
| `data/sample_thief.py`、`盗贼.txt` | `allin_engine/trpg/samples/` |
| `docs/*.md` | `allin_engine/trpg/docs/` |
| `web/`（TS WebExtension 实验区） | `web/trpg/` |
| `mvp_builder.py`、`mvp_gui.py` | **不迁**：转发到 `cli`/`gui` 的兼容壳，其目标单文件版本早已不存在，全量 grep 无任何外部引用 |

验收：`python -m allin_engine.trpg.samples.sample_thief` 的输出与黄金样例 `盗贼.txt`
的 12 个稳定关键字段**逐字段一致**（属性/优点/缺点/天赋/技术/HP 65 | AC 20/近战+11 远程+8/三豁免）。

## 本地字体加载

引擎支持加载本地字体，并兼容 `ALLIN_FONT_PATH` / `ALLIN_FONTS_DIR` 环境变量、系统字体与
pygame/tkinter 多重兜底。

> **字体不随包分发。** 手写体单个约 50MB，随包会让 wheel 从约 340KB 膨胀到 27MB，因此
> 字体只在源码仓库内保留，安装包不含它。缺字体时会自动降级到系统 CJK 字体，功能不受影响。

字体查找顺序：

1. `ALLIN_FONTS_DIR` 环境变量（字体目录）
2. `<包>/fonts/`（开发环境；或自行放入包目录）
3. `<资源根>/fonts/`
4. **用户数据目录**（推荐的存放位置，不存在会自动创建）
   - Windows：`%APPDATA%\allin_engine\fonts\`
   - Linux/macOS：`~/.local/share/allin_engine/fonts/`

此外 `ALLIN_FONT_PATH` 可直接指定单个字体文件。

源码仓库内的目录结构（供本地开发，不随包发布）：
```
allin_engine/
└── fonts/
    └── BaoCanMouHuiTingShouXieTi2.0-2.ttf   # 手写体
```

Pygame 端：
```python
from allin_engine.utils.font import load_local_font, load_cjk_font

# 加载本地字体（默认取 fonts/ 中第一个发现的字体）
font = load_local_font(32, bold=True)
font.render("饱餐谋·文字冒险", True, (255, 255, 255))

# 按别名加载（别名 = 文件名 stem，大小写不敏感）
font = load_local_font(24, name="baocanmou")

# 让通用 CJK 加载器优先使用本地字体
font = load_cjk_font(16, local_first=True)
```

Tkinter 端（GUI 标题/按钮用手写体，正文保持系统等宽可读性）：
```python
from allin_engine.render.gui_base import get_default_fonts

fonts = get_default_fonts(local_font="baocanmou")  # title/heading/button 用手写体
```

常用 API：
| 函数 | 说明 |
|------|------|
| `discover_local_fonts()` | 扫描 `fonts/` 目录，返回 `[(别名, 路径), ...]` |
| `load_local_font(size, name, bold, face_index)` | 从本地加载 pygame 字体 |
| `load_local_tk_font(size, name, bold)` | 从本地加载 tkinter 字体 |
| `register_local_font(alias, path)` | 手动注册字体别名 |
| `get_default_local_font_name()` | 返回默认本地字体别名 |
| `get_fonts_dir()` | 返回本地字体目录（兼容开发/pip/PyInstaller） |

> 支持格式：`.ttf` `.otf` `.ttc`（多字脸用 `face_index`）`.woff` `.woff2`。
> 字体对象按 `(路径, 字号, 粗体, 字脸)` 缓存，重复加载大体积 TTF 不会重复开销。

## Python 版本

Python 3.10+

## 可选依赖

| 依赖 | 用途 | 安装组 |
|------|------|--------|
| numpy | 音频合成、公式引擎、粒子系统 | render, audio |
| scipy | 音频信号处理 | audio |
| pygame-ce | 音频播放、输入、字体 | pygame |
| asteval | 公式引擎安全求值 | render |
| requests | AI DeepSeek 后端 | ai |

## 许可

MIT
