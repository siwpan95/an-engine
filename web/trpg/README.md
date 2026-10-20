# D20 web — Cordis 式浏览器扩展（TypeScript 移植）

D20 角色构筑器（D&D/GURPS 变体）的浏览器插件版。以 `G:/notpython/deepseek-harness-master`
为架构参考（React 18 + Vite + Cordis「上下文/服务/依赖注入/组合装配」），把原纯 Python
实现（`G:\repos\d20\d20`，1920 行核心逻辑）**1:1 移植为 TypeScript**，并包装成 WebExtension
（MV3，popup 入口）。子系统即 Cordis 服务，可在运行时**热挂载 / 卸载**（web-cordis 风格）。

## 架构

```
Character 门面（Proxy 状态透明代理 → ctx.state）
  ├── ctx.attributes   AttributesService   属性购买
  ├── ctx.equipment    EquipmentService    装备系统
  ├── ctx.perks        PerksService        优点/缺点/天赋
  ├── ctx.skills       SkillsService       技能购买与默认值推算
  ├── ctx.techniques   TechniquesService   技术（战技/法术）
  ├── ctx.derived      DerivedService      HP/AC/攻击/豁免
  ├── ctx.combat       CombatService       战斗宏
  ├── ctx.dice         DiceService         骰子检定
  ├── ctx.sheet        SheetService        角色卡渲染
  ├── ctx.slots        SpellSlotsService  法术位（独立 CP 购环 + 上环施法）
  ├── ctx.feats        FeatsService        专长（SRD 12 款，事件钩子生效）
  ├── ctx.race         RaceService         种族（9 族 GURPS 式模板定价）
  ├── ctx.background   BackgroundService   背景（6 款，+2 熟练）
  └── ctx.rest         RestService         先攻/休整（current_hp 追踪）
装配：composition.ts（TS 常量）/ public/composition.yml（cordis.yml 风格，可运行时加载）
      → loader.ts 按 inject 依赖拓扑排序 → ctx.mount
核心：engine/core.ts 自带零依赖 mini-Cordis（Context/Service/EventBus/effect 生命周期）
插件：engine/index.ts 导出 d20Plugin(ctx, options) → 挂入任意遵循契约的宿主 Context
```

与 deepseek-harness 的关系：其 `web-cordis` 示例是一个浏览器界面，在内存里
`mount/unmount` Cordis 插件。本项目的「插件」面板复刻同一交互：14 个服务可逐个
热挂载/卸载，卸载被依赖的服务后对应能力即报错（插件影响范围可见）。

## 文件映射（Python → TypeScript）

| Python（`G:\repos\d20\d20`） | TypeScript（src/engine） |
| --- | --- |
| core.py | core.ts（Context/Service/EventBus） |
| data.py | data.ts（规则数据中枢） |
| attributes.py | attributes.ts |
| equipment.py | equipment.ts |
| perks.py | perks.ts |
| techniques.py | techniques.ts |
| skills.py | skills.ts |
| dice.py | dice.ts |
| derived.py | derived.ts |
| combat.py | combat.ts |
| sheet.py | sheet.ts |
| character.py | character.ts（CharacterState + 门面） |
| loader.py + composition.yml | loader.ts + composition.ts + public/composition.yml |
| slots.py | slots.ts（法术位，独立 CP 购环 + 上环） |
| feats.py | feats.ts（专长，事件钩子） |
| race.py | race.ts（种族，GURPS 式模板定价） |
| background.py | background.ts（背景，+2 熟练） |
| rest.py | rest.ts（先攻/休整，current_hp） |

## 开发与构建

```sh
npm install          # react / vite / typescript
npm run dev          # Vite 开发服务器（浏览器页面模式预览）
npm run build        # tsc --noEmit 类型检查 + vite build → dist/
```

## 零依赖运行时验证（不启动浏览器）

```sh
npx tsc -p tsconfig.smoke.json   # 把纯引擎层 emit 成 CJS 到 dist-smoke/
node smoke.cjs                   # 25 项行为检查 + 11 项与 Python 基准的盗贼复刻比对
```

验证项包括：属性/技能/装备/技术/战斗宏/法术位/专长/种族/背景/休整全链路、14 服务挂载契约、
`derived` 服务卸载后 `hp()` 报错（插件影响）、**与 Python `data/sample_thief.py` 基准完全
一致的 11 项数值**（CP=1 / HP=65 / AC=20 / 近战+11 / 远程+8 / 强韧+11 / 反射+10 / 意志+10 /
默认值 / 调整值），以及 **30 项扩充子系统与 Python `tests/test_expansion.py` 逐值一致**。

## 安装为浏览器扩展

1. `npm run build` 生成 `dist/`（含 `manifest.json`、`index.html`、`composition.yml`、`assets/`）。
2. Chrome/Edge 打开 `chrome://extensions`，开启「开发者模式」→「加载已解压的扩展程序」→ 选择本项目的 `<仓库根>\web\dist` 目录（即上一步 `npm run build` 产出的 `web/dist/`）。
3. 点击工具栏图标打开 popup 即可使用。
