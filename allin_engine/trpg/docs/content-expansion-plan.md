# D20 内容扩充方案 — 5 个新规则子系统（Cordis 插件）

> 状态：**调研方案（待审阅）**。确认后按「Python d20/ 与 web/src/engine/ 同步实施」落地。
> 调研日期：2026-08-27，联网检索 D&D 5e SRD 官方资料完成。

## 0. 总览

在现有 9 个 Service（attributes/equipment/perks/skills/techniques/derived/combat/dice/sheet）
之上，新增 5 个 Cordis 插件：

| # | 新服务 | 挂载 key | inject 依赖 | 规则来源 |
|---|---|---|---|---|
| 1 | 法术位 SpellSlotsService | `slots` | [skills, techniques] | D&D 5e 全施法者法术位表 |
| 2 | 专长 FeatsService | `feats` | [perks, skills, derived] | D&D 5e SRD Feats |
| 3 | 种族 RaceService | `race` | [perks] | D&D 5e SRD Races（9 族） |
| 4 | 背景 BackgroundService | `background` | [skills] | D&D 5e SRD Backgrounds（6 款） |
| 5 | 先攻/休整 RestService | `rest` | [derived, dice, slots] | D&D 5e Initiative / Rest 规则 |

新增 `composition.yml` 条目（按 inject 拓扑排在 derived/sheet 之间）：

```yaml
- id: race        service: RaceService        inject: [perks]
- id: background  service: BackgroundService  inject: [skills]
- id: slots       service: SpellSlotsService  inject: [skills, techniques]
- id: feats       service: FeatsService       inject: [perks, skills, derived]
- id: rest        service: RestService        inject: [derived, dice, slots]
```

**CharacterState 新增字段**：`race`、`background`、`feats: list[str]`、`slots_used: dict[str,int]`（各环已用数）、`current_hp`。

---

## 1. 法术位（SpellSlotsService）

**设计**：D20 无职业等级，施法者等级轴 = 现有「奥术施法」技能**有效等级**（与 HP 随「活力」等级成长同一模式）。法术位表随施法者等级增长，无需另买 CP——成本已含在奥术施法（VH 难度）的技能 CP 中。

**全施法者法术位表（SRD，施法者等级 1–20 → 各环可用数）**：

| 施法者等级 | 1环 | 2环 | 3环 | 4环 | 5环 | 6环 | 7环 | 8环 | 9环 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | — | — | — | — | — | — | — | — |
| 2 | 3 | — | — | — | — | — | — | — | — |
| 3 | 4 | 2 | — | — | — | — | — | — | — |
| 4 | 4 | 3 | — | — | — | — | — | — | — |
| 5 | 4 | 3 | 2 | — | — | — | — | — | — |
| 6 | 4 | 3 | 3 | — | — | — | — | — | — |
| 7 | 4 | 3 | 3 | 1 | — | — | — | — | — |
| 8 | 4 | 3 | 3 | 2 | — | — | — | — | — |
| 9 | 4 | 3 | 3 | 3 | 1 | — | — | — | — |
| 10 | 4 | 3 | 3 | 3 | 2 | — | — | — | — |
| 11 | 4 | 3 | 3 | 3 | 2 | 1 | — | — | — |
| 12 | 4 | 3 | 3 | 3 | 2 | 1 | — | — | — |
| 13 | 4 | 3 | 3 | 3 | 2 | 1 | 1 | — | — |
| 14 | 4 | 3 | 3 | 3 | 2 | 1 | 1 | — | — |
| 15 | 4 | 3 | 3 | 3 | 2 | 1 | 1 | 1 | — |
| 16 | 4 | 3 | 3 | 3 | 2 | 1 | 1 | 1 | — |
| 17 | 4 | 3 | 3 | 3 | 2 | 1 | 1 | 1 | 1 |
| 18 | 4 | 3 | 3 | 3 | 3 | 1 | 1 | 1 | 1 |
| 19 | 4 | 3 | 3 | 3 | 3 | 2 | 1 | 1 | 1 |
| 20 | 4 | 3 | 3 | 3 | 3 | 2 | 2 | 1 | 1 |

**与技术库接驳**：现有 TECHNIQUES 里法术已有环位（魔法飞弹/治疗言灵 = 1 环，火球术 = 3 环）。
为技术条目补充第 8 字段 `ring`（环位，0=戏法/非法术），施法时 `spend_slot(ring)` 校验：
不足则返回「无可用 X 环法术位」。法术技术新增：戏法「火焰箭 1d10」「霜冻射线 1d8」、
1 环「护盾术 +5AC」「治愈真言」、2 环「人类定身」「灼热射线 3×2d6」、3 环「闪电束 8d6」、
5 环「寒冰锥 8d8」、9 环「陨石雨 40d6」——数据取 SRD。

**新增方法**：`slot_table()`（当前各环可用/已用）、`spend_slot(ring)`、`short_rest_recovery()`（法师奥术恢复：短休回总等级一半的环位，参考 Arcane Recovery）。

**上环施法（Upcasting）**：战斗宏加参数 `upcast=N`：火球术每 +1 环 +1d6（SRD：8d6→9d6→10d6）；魔法飞弹每 +1 环 +1 发。宏输出注明所耗环位。

---

## 2. 专长（FeatsService）

**设计**：与现有「优点」（GURPS 式，2–30 CP）区分——专长是 **D&D 式、带前置条件、可挂事件钩子** 的新子系统（第一个有 attribute/skill 前置校验的插件）。定价按 SRD 强度分档：半专长（含 +1 属性）8 CP，标准专长 12 CP，战斗强专长 15 CP。

**SRD 专长精选（12 款，映射到 D20 数值系统；D20 无优势机制，advantage 折算 +2）**：

| 专长 | 前置 | CP | D20 效果（实现点） |
|---|---|---|---|
| 警觉 Alert | — | 12 | 先攻 +5（rest.initiative 读 feats） |
| 运动员 Athlete | — | 8 | 力量或敏捷 +1（选一，上限20） |
| 演员 Actor | — | 8 | 魅力 +1；欺瞒/表演 检定 +2 |
| 防御决斗者 Defensive Duelist | 敏捷≥13 | 12 | 装备灵巧武器被近战命中时，反应 +2 AC（combat 钩子） |
| 双持大师 Dual Wielder | — | 12 | 双持两把近战武器时 AC +1 |
| 顽强 Durable | — | 8 | 体质 +1；短休掷生命骰最少回复 2×体质调整 |
| 元素亲和 Elemental Adept | 可施法 | 12 | 选一元素（酸/寒/火/电/雷），该元素伤害骰 1 视为 2（dice 钩子） |
| 巨武宗师 Great Weapon Master | — | 15 | 双手武器：命中 −5、伤害 +10（combat 宏参数） |
| 幸运 Lucky | — | 15 | 每日 3 次 d20 重掷（dice 钩子，状态计数） |
| 观察力 Observant | — | 8 | 侦察/调查 检定 +2 |
| 神射手 Sharpshooter | — | 15 | 远程：命中 −5、伤害 +10（combat 宏参数） |
| 强壮 Tough | — | 12 | 最大 HP +2×活力等级（derived.max_hp waterfall 钩子） |

**Cordis 事件钩子示范**（本子系统最大架构卖点）：
- `derived/max_hp` 用 **waterfall** 计算——强壮专长在 mount 时注册 `(hp, next) => next(hp + 2*vit_rank)`；
- `dice/roll_d20` 用 **serial**——幸运专长注册重掷逻辑；
- `derived/initiative` 用 waterfall——警觉专长 +5。
- 卸下专长插件（unmount feats）后这些加成随之消失——与 web 插件面板热卸载演示闭环。

---

## 3. 种族（RaceService）

**设计**：种族 = 创建期模板，**0 CP**（D&D 原味；GURPS 式种族定价可作为后续可选项）。
选择种族即应用属性加值（直接改 base attributes）并自动获得对应「优点」（复用现有
ADVANTAGES_LIBRARY，如黑暗视觉 8CP 由种族免费授予）。

**SRD 9 种族（含亚种）数据表**：

| 种族 | 属性加值 | 特性 → D20 映射 |
|---|---|---|
| 人类 | 全六属性 +1 | 无（最灵活） |
| 精灵 | 敏捷 +2 | 黑暗视觉(优点)、杂技+1 |
| · 高等精灵 | 智力 +1 | 额外：免费 1 个 0 环戏法 |
| · 木精灵 | 感知 +1 | 额外：先攻 +1（迅捷） |
| 矮人 | 体质 +2 | 黑暗视觉、毒素豁免 +2（矮人韧性） |
| · 丘陵矮人 | 感知 +1 | 额外：HP +1/活力等级 |
| · 山地矮人 | 力量 +2 | 额外：免中甲熟练需求 |
| 半身人 | 敏捷 +2 | 幸运(重掷1)、意志豁免 +2（勇敢） |
| · 轻足半身人 | 魅力 +1 | 额外：躲藏 +2 |
| · 壮实半身人 | 体质 +1 | 额外：毒素豁免 +2 |
| 侏儒 | 智力 +2 | 黑暗视觉、心智豁免 +2（侏儒狡黠） |
| · 岩侏儒 | 体质 +1 | 额外：调查 +2 |
| 半精灵 | 魅力 +2、另两项自选 +1 | 黑暗视觉、免魅惑优势(→意志豁免+2) |
| 半兽人 | 力量 +2、体质 +1 | 黑暗视觉、濒死不屈(Relentless)、暴击伤害+1骰 |
| 龙裔 | 力量 +2、魅力 +1 | 龙息武器（combat 宏：2d6 元素喷吐，短休充能） |
| 提夫林 | 魅力 +2、智力 +1 | 黑暗视觉、火焰抗性(→火焰伤害减半) |

**新增方法**：`set_race(name)`（仅可在未购买任何内容前调用，或允许重建时重选）、`racial_bonuses()`。

---

## 4. 背景（BackgroundService）

**设计**：背景 = 创建期模板，**0 CP**，授予 2 项技能「熟练」。
D20 无熟练加值概念 → 方案：**免费 +1 技能等级**（与 2014 SRD 的两技能熟练对应；
2024 版的 +2/+1 属性与起源专长作为 config 可选项，默认关闭）。
另附叙事特性字符串（入角色卡）。

**SRD 背景（2014 PHB 六款）**：

| 背景 | 技能（免费+1） | 特性（叙事） |
|---|---|---|
| 侍僧 Acolyte | 洞察、宗教 | 神殿庇护（Shelter of the Faithful） |
| 罪犯 Criminal | 欺瞒、躲藏 | 犯罪人脉（Criminal Contact） |
| 民间英雄 Folk Hero | 驯兽、生存 | 乡民好客（Rustic Hospitality） |
| 贵族 Noble | 历史、说服 | 特权身份（Position of Privilege） |
| 学者 Sage | 奥术知识、历史 | 研究者（Researcher） |
| 士兵 Soldier | 运动、恐吓 | 军衔（Military Rank） |

**新增方法**：`set_background(name)`（免费 +1 至对应技能，超上限无效并提示）、`background_feature()`。
角色卡「背景」行：`背景: 罪犯（犯罪人脉）`。

---

## 5. 先攻 / 休整（RestService）

**设计**：补上 D20 目前缺失的战斗外围闭环。需要引入 **current_hp** 状态（与 max_hp 分开）。

- **先攻**：`initiative_bonus = 敏捷调整 + 种族/专长/优点加成（waterfall）`；
  `roll_initiative()` = d20 + 加值，返回可读串。警觉专长 +5、木精灵 +1、战斗反射（现有优点）+1。
- **短休**：花 1 个生命骰（1d6 + 体质调整，快速回复优点翻倍，顽强专长保底 2×体质调整），
  生命骰数 = 活力等级；回复 `current_hp`。
- **长休**：`current_hp = max_hp`，法术位全部恢复，生命骰恢复一半（SRD），每日能力（幸运等）重置。
- **新增状态**：`current_hp`（默认 = max_hp）、`hit_dice_used`、`lucky_used`。

**新增方法**：`roll_initiative()`、`short_rest()`、`long_rest()`、`take_damage(n)`、`heal(n)`。
combat 宏与 UI 显示 `HP: current/max`。

---

## 6. 测试与验证计划

1. **Python 侧**：`tests/test_expansion.py` 新增测试（预计 +30 项）：
   法术位表边界（施法者等级 0/1/9/17/20）、上环施法、专长前置校验与效果钩子、
   种族属性加值与免费优点、背景免费技能、短休/长休数值、幸运重掷计数。
2. **Web 侧**：`smoke.cjs` 追加同套场景（TS 与 Python 逐值一致基准）。
3. **兼容性**：现有 129 项 Python 测试零改动、shim/GUI/sample 零改动（新增子系统默认不挂载或挂载后不影响既有行为——sheet 输出只新增行）。
4. **插件面板**：web UI 插件列表从 9 项变 14 项；演示「卸载 feats → HP/先攻回落」「卸载 slots → 施法宏报错」。

## 7. 待你拍板的设计决策

| # | 决策点 | 本方案默认 | 备选 |
|---|---|---|---|
| A | 法术位轴 | 随「奥术施法」有效等级（不另收费） | 独立 CP 购买每环位 |
| B | 专长定价 | 半专长 8 / 标准 12 / 强专长 15 | 统一 10；或并入优点库 |
| C | 种族成本 | 0 CP（D&D 原味） | GURPS 式模板定价 |
| D | 背景加成 | 免费 +1 技能等级 | +2 熟练加值（更贴 D&D） |
| E | 当前 HP | 引入 current_hp（休整需要） | 不追踪，休整仅重置每日能力 |
| F | 种族/背景选择时机 | 仅限创建期（购买内容前） | 任意时刻可换（重算） |

## 8. 实施顺序（确认后）

1. Python：data 扩充（法术位表/专长/种族/背景常量）→ 5 个 Service → composition.yml → 测试 → `pytest` 全绿。
2. Web：engine 同步 1:1 移植 → 插件面板扩至 14 项 → `tsc`/`vite build`/`smoke.cjs` 三方验证。
3. 双端 README 同步。

## 9. 调研来源

- 法术位表：https://theendlessness.com/blog/spell-slots-explained 、https://5e.d20srd.org/srd/classes/wizard.htm
- 专长：https://www.dandwiki.com/wiki/5e_SRD:Feats 、https://blackcitadelrpg.com/?p=2272
- 种族：https://dndcrunch.com/reference/races 、https://www.dandwiki.com/wiki/5e_SRD:Elf
- 背景：https://www.roll20.net/compendium/dnd5e/Backgrounds%20by%20Name 、https://spinforcharacter.com/backgrounds

---

## 10. 来源、许可与不入仓声明（借鉴必记账）

| 项 | 内容 |
| --- | --- |
| 上游 | **D&D 5e SRD**（https://dndcrunch.com/reference/races 、https://www.dandwiki.com/wiki/5e_SRD:Elf 等，见 §9 调研来源） |
| 许可证 | D&D 5e SRD 采用 **CC BY 4.0**（署名即可用）；本仓整体为 MIT（见 `LICENSE`），规则数据为**按 SRD 数值自行实现**，不复制上游文本 |
| 借鉴范围 | 规则**数值与公式**（技能表 / 装备伤害骰 / 法术伤害骰 / 优缺点点值），及其它系统设计思路 |
| 不入仓声明 | 上游原文与页面**不随本仓分发**（仅链接引用）；规则数据的权威实现落在引擎 `allin_engine.trpg.data`，本仓只做转发 |
