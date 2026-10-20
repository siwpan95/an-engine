# Cordis 信息调研报告

> 调研目的：为「以 `deepseek-harness-master` 为参考重构本仓（原 `E:/D20`，现 `G:\repos\d20`）」提供 Cordis 框架的事实底座。
> 调研方式：本地 vendored 源码 + 官方文档（`deepseek-harness-master/vendor/cordis`、`docs/cordis-primer.md`）+ 联网检索（2026-08-27）。
> 适用结论：D20 是纯 Python 项目，Cordis 本体是 TypeScript/ESM，因此本调研给出的是**架构思想与机制**的可移植映射，而非直接引入 TS 依赖。

---

## 1. Cordis 是什么

Cordis 是一个面向 Node.js/TypeScript 的**插件元框架（meta-framework）**，由 DeepSeek 团队 vendored 进 `deepseek-harness`（`vendor/cordis`，npm 包名 `@deepseek-ai/cordis`，上游 `cordis` 单仓约 5.5k★ / MIT）。它把四件事合并到同一套 `Context`/`Fiber` 模型里：

- **依赖注入（DI）** —— 插件通过 `inject` 声明所需服务，框架等依赖就绪再启动，不靠手写启动顺序。
- **事件总线** —— 插件间用 `emit` / `waterfall` / `parallel` / `serial` 四种语义通信。
- **生命周期管理** —— 每个插件是一个 `Fiber`，挂载即实例化、卸载即回收它登记的一切。
- **配置驱动 + 隔离 + 热更新** —— 用 `cordis.yml` 描述插件树，`isolate` 派生独立服务作用域，`effect` 跟踪副作用以支持热插拔。

一句话定位（来自社区解读）：它不是 Express/Koa 式中间件，也不是单纯 DI 容器，而是把 **DI + 事件 + 生命周期 + 配置覆盖 + 隔离上下文 + 热更新** 统一进同一模型的 meta-framework；其核心卖点是「**时空可组合性（spatiotemporal composability）**」——上下文像 Git 分支一样 `fork`/`dispose`，换插件不用重启进程、不丢运行时状态。

---

## 2. 五大核心概念（官方 Primer）

| 概念 | 含义 |
|---|---|
| **Plugin（插件）** | 被加载的代码单位。可以是带 `apply(ctx, config)` 的函数，也可以是继承 `Service` 的类；有生命周期，卸载时回收它登记的一切。 |
| **Context（上下文）** | 服务的容器（仓库）。一个服务占据稳定的 `ctx.<key>`（如 `ctx.tools`、`ctx.llm`、`ctx.sessions`）；其他插件**按 key 查找服务而非 import 具体实现**。 |
| **inject（依赖注入）** | 插件用 `inject: ['tools']` 声明所需服务，框架等该服务存在才调用 `apply`；加载顺序由依赖表达。 |
| **Typed Events（类型化事件）** | 通过 TS declaration merging 声明事件名；四种分发模式对应「观察 / 包装 / 并行扇出 / 按序执行」。 |
| **Reversible Effects（可逆副作用）** | 提示片段、工具 schema、适配器、监听器、资源都通过 `ctx.effect()` / `ctx.on()` 注册，卸载时自动回滚——这是运行时热插拔的前提。 |

---

## 3. 关键机制（来自 vendored 源码）

### 3.1 Context 是代理（proxy）
`new Context()` 返回的是 `Proxy`。普通属性读取走服务解析器（`ReflectService`）：
- 子上下文**原型继承**父上下文的全部属性；`extend()` 派生带附加元数据的子上下文，不修改父。
- `isolate(name, label)` 为某个服务名创建一个独立作用域：该名下的读写在新 label 下解析，父作用域不受影响（解决「同一服务多实现」问题，如一个 preset 真正拥有某项服务）。
- `intercept(name, config)` 为某服务的 per-plugin 配置做合并拦截。

### 3.2 Service 注册
`class Counter extends Service { constructor(ctx){ super(ctx, 'counter') } }`。`super(ctx, key)` 把能力挂到 `ctx.<key>`。其他插件 `ctx.counter.next()` 即可调用，无需 import 具体类。

### 3.3 inject 解决加载顺序
`greeter.inject = ['counter']` → 框架等 `counter` 服务就绪再运行 `greeter`。菱形依赖（A、B 都依赖 DB）优雅解决：只存在一个实例，且它比使用它的插件活得久。

### 3.4 事件四种分发模式（公共契约的一部分）
| 模式 | 是否 await | 顺序 | 有返回值? |
|---|---|---|---|
| `emit` | 否 | 注册顺序观察 | 否 |
| `waterfall` | 否 | 注册顺序（around 中间件） | 是 |
| `parallel` | 是 | 全部并行 | 否 |
| `serial` | 是 | 注册顺序 | 是 |

`waterfall` 是 around-middleware：监听者收到 `(...args, next)`，调用 `next()` 把（可能被包装的）结果委托给下一个；不调用 `next()` 即短路。`prepend: true` 用于必须排在最前的监听者。

### 3.5 Effect 与生命周期（Fiber）
- `ctx.effect(fn)` 立即执行 `fn`，收集它产生的所有 disposer，在 fiber 卸载（或 disposer 被调用）时**逆序**执行清理。
- `Fiber` 状态机：`PENDING → LOADING → ACTIVE → (UNLOADING) → DISPOSED`，外加 `FAILED`。依赖未齐时为 PENDING，依赖齐了才 `_reload()` 跑插件体；依赖消失则 `_unload()` 回收。
- 卸载时所有 effect（定时器、监听器、DB 连接、注册的 schema）自动逆序清理，因此「换一个插件文件 = 只重建受影响的上下文子树，不丢 WebSocket / session / 缓存」。

### 3.6 配置校验
插件可带 `Config` 标准 schema；`ctx.plugin(Runtime, config)` 启动前用 `standard-schema` 校验，失败抛 `ValidationError`，绝不静默跳过缺失引用（与 dsh 的「Misconfiguration fails loud」一致）。

---

## 4. 加载与配置驱动（Loader / cordis.yml）

- `@cordisjs/plugin-loader` + `@cordisjs/plugin-include` 从 YAML/JSON 加载插件树。
- `cordis.yml` 每行是一个插件条目：`id` / `name`（包或绝对路径）/ `config` / `disabled` / `group` / `isolate`。
- `!!js` 仅在插件 `config` 与条目 `disabled` 下求值（如 `disabled: !!js process.platform === 'win32'`），其余元数据保持字面量；条件组合用 overlay。
- `cordis:group` 行（带 `group: true`）把一个子树包进一个 isolate 作用域（见下节 preset 示例）。

---

## 5. deepseek-harness 怎么用它（参考样板）

`AGENTS.md` 第一条：**everything is a plugin**。关键实践：

- **两平面（two planes）**：HOST 组合持有跨会话共享的注册表（持久化、沙箱、审批栈、模型路由、子代理注册表）；AGENT PRESET 持有一个会话贡献的内容（工具、persona、prompt 片段）。发布服务的行属于 host 平面（或 `isolate` 领域），否则进 preset。
- **能力接缝（capability seam）= Service Definition + Provider + Consumer** 三角色，缺一不可。
- **最小插件**：`export function apply(ctx){ ctx.on('ready', ...) }`，通过绝对路径 `cordis.yml` overlay 挂载。
- **策略插件**走 `tools/pre-execute`（放行/拒绝/审批）、`tools/execute`（deadline/重试/metrics）、`tools/post-execute`（结果变换）、`tools/result`（审计/metrics）等文档化事件缝，而非随便塞监听。
- **可逆注册**：`ctx.tools.register(...)` 返回 disposer；自定义资源（定时器/网络客户端）用 `ctx.effect(() => { ...; return () => clearInterval(t) })`。
- **工程规范（值得 D20 借鉴）**：`AGENTS.md` 写明约定；每包有 README；不变量（invariant）测试；显式 > 隐式；配置项可经 `cordis.yml` 改、常量不算可配置；改动必同步文档与测试。

示例（`apps/cli/config/agent-presets/cordis/agent.cordis.yml` 节选，展示 `group` + `isolate` + 条件 `disabled`）：
```yaml
- id: planning
  name: cordis:group
  group: true
  isolate: { planMode: true }
  config:
    - id: plan-mode
      name: '@deepseek-ai/dsh-plan-mode'
      config: { section: "You are in plan mode. ..." }

- id: tool-bash
  name: '@deepseek-ai/dsh-tool-bash'
  disabled: !!js process.platform === 'win32'
```

---

## 6. 与 D20 的映射 & 重构设计提案

D20 现状：`Character(AttributesMixin, EquipmentMixin, PerksMixin, SkillsMixin, TechniquesMixin, DerivedMixin, CombatMixin, DiceMixin, SheetMixin)` —— 9 个 mixin 多重继承，`__init__` 集中初始化全部实例状态。这正是 Cordis 要解决的「静态初始化树」反模式：加一套新规则系统（如「法术位 / 专长 / 背景」）必须改 `Character` 类与 MRO，无法按依赖解耦、无法热插拔、无显式装配声明。

**建议的 Python 版 mini-Cordis（落在 `d20/core.py`）**，把上述机制可移植为 Python 惯用法：

| Cordis | D20 Python 等价 |
|---|---|
| `Context` | `Context`：服务容器 + 生命周期 + 事件总线（代理或直接 dict 解析） |
| `Service` | `class AttributesService(Service)` 等 9 个子系统服务，挂到 `ctx.attributes` / `ctx.equipment` … |
| `inject` | 服务类声明 `inject = ['attributes','equipment']`，框架等依赖就绪再 mount |
| 4 模式事件 | `ctx.emit/on` / `ctx.waterfall` / `ctx.parallel` / `ctx.serial`（用同步+async 适配） |
| `effect` / `dispose` | `ctx.effect(fn)` 收集 disposer，unmount 逆序清理 |
| `Fiber` 生命周期 | `Plugin` 挂载/卸载状态机 + `await()` |
| `cordis.yml` | `composition.yml`（或 `composition.py`）声明装载哪些子系统及配置 |

**装配改法（保留公共 API 不变）**：
1. 新增 `d20/core.py`：实现 `Context` / `Service` / `Plugin` / 事件总线 / `effect` 机制（约 150–250 行，零外部依赖）。
2. 把 9 个 mixin 改写为 `Service` 子类（能力方法移到服务上，共享状态仍由 `Character` 持有，服务读写 `ctx.state`）。每个服务声明 `inject` 依赖（如 `DerivedService` 注入 `attributes` + `equipment`）。
3. 新增 `d20/composition.py`：声明默认装配（`mount_default_composition(ctx)`），并可从 `composition.yml` 读取（可选）。D20 与 GURPS 可成为两个可切换的 preset 子树（`isolate` 领域）。
4. `Character` 退化为**门面（facade）**：持 `ctx` 与状态 dict，把所有老方法（`set_attribute` / `purchase_skill` / `combat_macro` / `show_sheet` …）与类级数据（`SKILL_LIBRARY` 等）委托/代理到对应服务 —— 因此 `mvp_builder` shim、`sample_thief.py`、`gui/app.py`、122 项测试**零改动通过**。
5. 加事件缝：如 `character/changed` 让 `Sheet`/`Combat` 在状态变更时重算衍生值，替代现在的隐式调用。

**兼容约束（不可破坏）**：
- 公共 API：`c.set_attribute / attr_mod / add_advantage / add_disadvantage / add_talent / purchase_skill / purchase_technique / equip_item / show_sheet / combat_macro / gurps_check / d20_check / d100_check / roll_d6` 等方法签名不变。
- 类级数据：`SKILL_LIBRARY / EQUIPMENT_LIBRARY / ATTRIBUTES / TECHNIQUES / TALENT_BONUS_GROUPS / ADVANTAGES_LIBRARY / DISADVANTAGES_LIBRARY / FINESSE_WEAPONS / WEAPON_DICE` 等仍可作 `char.<X>` 访问。
- 实例状态：`char.cp / attributes / skills / equipment / advantages / disadvantages / talents / techniques` 保持可访问。
- `python -m pytest tests/ -v` 122 passed 必须仍然全绿。

---

## 7. 风险与权衡

- **风险**：mixin → service 改写若委托层没对齐，可能悄悄改变行为；必须用 122 测试 + 一个「装配后行为一致性」冒烟来验证（如 `sample_thief` 输出与 `盗贼.txt` 一致）。
- **收益**：规则系统从「改类」变为「挂插件」——新增 D&D 法术位 / GURPS 魔法 / 背景包等只是加一个 `Service` + 一行 `composition`，不改 `Character`；依赖显式、可测试、可热插拔；直接对齐 `deepseek-harness` 的架构语言，便于后续把 D20 接进 harness 做 agent 化。
- **不做**：不引入 TS/Node 运行时；不引入 YAML 解析库（除非确认需要，标准库 `yaml` 或自写极简 loader 即可）；不破坏现有公共 API 与测试。

---

## 8. 参考资料

- 本地：`G:/notpython/deepseek-harness-master/vendor/cordis/src/{context,fiber,events,reflect,registry,utils}.ts`
- 本地：`G:/notpython/deepseek-harness-master/docs/cordis-primer.md` 与 `docs/cordis-tutorial/`
- 本地示例：`apps/cli/config/agent-presets/cordis/agent.cordis.yml`、`examples/web-cordis/cordis.yml`
- 社区解读：
  - Cordis 架构概览（starlog.is）：https://starlog.is/articles/developer-tools/cordiverse-cordis
  - DeepSeek Harness 插件开发（qubittool.com）：https://qubittool.com/blog/deepseek-harness-plugin-development
  - 每天一个开源项目 #70 Cordis（掘金，中文）：https://juejin.cn/post/7674904635566145555
  - 解构 Cordis（CSDN，中文）：https://blog.csdn.net/gs80140/article/details/163752955
  - 从 Cordis 到 dsh：一切皆插件（CSDN，中文）：https://blog.csdn.net/qq_28077405/article/details/163847996
- 上游仓库：`cordis`（npm/GitHub，MIT，5.5k★）

---

## 9. 来源、许可与不入仓声明（借鉴必记账）

| 项 | 内容 |
| --- | --- |
| 上游 | **Cordis**（https://github.com/cordiverse/cordis ，MIT）；参考样板 **deepseek-harness**（本地 vendored 快照） |
| 许可证 | 上游均为 MIT；本仓同为 MIT（见 `LICENSE`） |
| 借鉴范围 | 仅**架构思想与机制映射**（Context 代理 / Service 注册 / inject / 事件分发 / Fiber 生命周期 / 配置校验），**不引入 TS 依赖、不复制上游源码** |
| 不入仓声明 | 上游源码**不随本仓分发**；本报告引用的 vendored 路径仅为**本机留档**，克隆本仓后不存在，需要者请自行获取上游 |
