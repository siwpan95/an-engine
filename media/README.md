# alloy/media —— 媒体子系统（J2 S2/S3 并入，2026-08-25）

- 来源：pywallpaper/engine + recipes（媒体引擎能力层）；效果内容层（effects/ JSON）与应用层（systems/）留在 pywallpaper。
- formula_engine.py：media 域公式引擎（自写解析器+回退求值）；与 render/formula_engine.py（asteval+模板，render 域）分层共存。
- primitives/：21 个效果原语（ca/ca_kernel/curve/formula/particle/fluid/...）。
- recipes/：CA 配方库（4972 个 JSON）。
- **ca/（J2 S3）**：通用 CA 规则引擎（自 cellular_automaton 并入）：141 规则 = Life-like 63 / Multi-state 9 / Complex 11 / 连续 58（Gray-Scott 23 + Lenia 6 + LtL 9 + 1D 15 + 其他 5），JSON 规则库 + RuleManager + CellularAutomaton。
  - 与 primitives/ca_kernel.py 分层共存：ca_kernel 是 pywallpaper 4973 配方语料的兼容层（配方按内核名取核），ca/ 是规则族超集引擎；不互相替代。
- 装配：`preset_media` / profile `media`（dump-profile 显示 media=FormulaEngine 服务）。
- 测试：test/test_media.py（5 项）。
