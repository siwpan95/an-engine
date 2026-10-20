import { useEffect, useReducer, useRef, useState } from "react";
import {
  Character, CharacterState, COMPOSITION, mountService, unmountService,
  ATTRIBUTES, SKILL_LIBRARY, EQUIPMENT_LIBRARY, TECHNIQUES,
  ADVANTAGES_LIBRARY, DISADVANTAGES_LIBRARY, TALENT_BONUS_GROUPS,
  RACE_TEMPLATES, BACKGROUNDS, FEATS_LIBRARY, ELEMENTS,
  DEFAULT_STARTING_CP, DEFAULT_MAX_DISADVANTAGE_CP,
} from "../engine";

const MACROS: Array<[string, string]> = [
  ["melee_attack", "近战攻击"], ["ranged_attack", "远程攻击"], ["sneak_attack", "偷袭攻击"],
  ["power_attack", "猛力攻击"], ["whirlwind", "旋风切割"], ["fireball", "火球术"],
  ["magic_missile", "魔法飞弹"], ["healing_word", "治疗言灵"], ["fire_bolt", "火焰箭"],
  ["ray_of_frost", "霜冻射线"], ["scorching_ray", "灼热射线"], ["lightning_bolt", "闪电束"],
  ["cone_of_cold", "寒冰锥"], ["meteor_swarm", "陨石雨"], ["dragon_breath", "龙息"],
  ["deceptive_attack", "欺诈攻击"], ["rapid_strike", "连环打击"],
  ["allout_strong", "全力强击"], ["allout_determined", "精准突击"],
];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="panel">
      <h2>{title}</h2>
      {children}
    </div>
  );
}

function safe<T>(fn: () => T, fallback: T): T {
  try { return fn(); } catch { return fallback; }
}

export function App() {
  const charRef = useRef<Character>();
  if (!charRef.current) charRef.current = new Character();
  const char = charRef.current;

  const [, force] = useReducer((x: number) => x + 1, 0);
  const [log, setLog] = useState<string[]>([]);

  useEffect(() => {
    const disp = char.ctx.on("character/changed", () => force());
    return disp;
  }, []);

  function act(msg: string) {
    setLog((l) => [msg, ...l].slice(0, 60));
    force();
  }
  function runMacro(name: string, label: string) {
    try {
      const out = char.combatMacro(name, {});
      setLog((l) => [`【${label}】\n${out}`, ...l].slice(0, 60));
    } catch (e: any) {
      setLog((l) => [`【${label}】出错: ${e?.message ?? e}`, ...l].slice(0, 60));
    }
    force();
  }

  function reset() {
    const ns = new CharacterState(DEFAULT_STARTING_CP, DEFAULT_MAX_DISADVANTAGE_CP);
    (char as any).state = ns;
    char.ctx.state = ns;
    setLog((l) => ["已重置角色", ...l].slice(0, 60));
    force();
  }

  // 插件面板：运行时挂载/卸载单个服务
  const [pluginMsg, setPluginMsg] = useState("");
  function togglePlugin(id: string, enabled: boolean) {
    try {
      if (enabled) {
        const entry = COMPOSITION.find((e) => e.id === id)!;
        mountService(char.ctx, entry);
        setPluginMsg(`已挂载服务: ${id}`);
      } else {
        unmountService(char.ctx, id);
        setPluginMsg(`已卸载服务: ${id}（依赖它的能力将不可用，演示插件影响）`);
      }
    } catch (e: any) {
      setPluginMsg(`操作失败: ${e?.message ?? e}`);
    }
    force();
  }

  const st: CharacterState = char.state;
  const hp = safe(() => char.hp(), NaN);
  const ac = safe(() => char.ac, NaN);
  const atkM = safe(() => char.attackBonus(true), NaN);
  const atkR = safe(() => char.attackBonus(false), NaN);
  const curHp = safe(() => (char.ctx.rest as any).currentHp(), NaN);
  const init = safe(() => (char.ctx.rest as any).initiativeBonus(), NaN);

  return (
    <div>
      <h1>D20 角色构筑器 <span className="badge">Cordis 式浏览器插件</span></h1>
      <div className="sub">
        纯 TypeScript 移植（参考 deepseek-harness 架构）。14 个子系统即 Cordis 服务，可在下方「插件」面板运行时热挂载 / 卸载。
      </div>

      <div className="panel">
        <div className="stat-grid">
          <div className="stat"><div className="k">剩余 CP</div><div className="v cp">{st.cp}</div></div>
          <div className="stat"><div className="k">HP</div><div className="v">{Number.isNaN(hp) ? "—" : (Number.isNaN(curHp) || curHp === hp ? hp : `${curHp}/${hp}`)}</div></div>
          <div className="stat"><div className="k">AC</div><div className="v">{Number.isNaN(ac) ? "—" : ac}</div></div>
          <div className="stat"><div className="k">先攻</div><div className="v">+{Number.isNaN(init) ? "?" : init}</div></div>
          <div className="stat"><div className="k">近战攻击</div><div className="v">+{Number.isNaN(atkM) ? "?" : atkM}</div></div>
          <div className="stat"><div className="k">远程攻击</div><div className="v">+{Number.isNaN(atkR) ? "?" : atkR}</div></div>
        </div>
        <div className="row" style={{ marginTop: 10 }}>
          <button className="danger" onClick={reset}>重置角色</button>
          <span className="hint">优点/缺点返还上限：{st.maxDisadvantageCp}</span>
        </div>
      </div>

      <Section title="创建（种族 / 背景，仅创建期）">
        <div className="row">
          <select id="race-sel"><option value="">— 种族 —</option>{Object.entries(RACE_TEMPLATES).map(([k, v]) => <option key={k} value={k}>{k} ({v.cp}CP)</option>)}</select>
          <button onClick={() => { const v = (document.getElementById("race-sel") as HTMLSelectElement).value; if (!v) return; const [ok, m] = char.setRace(v); act(m); }}>选择种族</button>
          <select id="bg-sel"><option value="">— 背景 —</option>{Object.keys(BACKGROUNDS).map((k) => <option key={k} value={k}>{k}</option>)}</select>
          <button onClick={() => { const v = (document.getElementById("bg-sel") as HTMLSelectElement).value; if (!v) return; const [ok, m] = char.setBackground(v); act(m); }}>选择背景</button>
        </div>
        <div style={{ marginTop: 8 }}>
          <span className="tag">种族: {st.race || "无"}</span>
          <span className="tag">背景: {st.background || "无"}</span>
          {st.proficiencies.map((p) => <span className="tag" key={p}>熟练:{p}+2</span>)}
        </div>
      </Section>

      <Section title="属性">
        {ATTRIBUTES.map((attr) => (
          <div className="attr-row" key={attr}>
            <span className="name">{attr}</span>
            <span className="val">{st.attributes[attr]}</span>
            <span className="badge">{(char.attrMod(attr) >= 0 ? "+" : "") + char.attrMod(attr)}</span>
            <button onClick={() => { const [ok, m] = char.setAttribute(attr, st.attributes[attr] - 1); if (ok) act(m); else act(m); }}>−</button>
            <button onClick={() => { const [ok, m] = char.setAttribute(attr, st.attributes[attr] + 1); if (ok) act(m); else act(m); }}>＋</button>
          </div>
        ))}
      </Section>

      <Section title="优点 / 缺点 / 天赋">
        <div className="row">
          <select id="adv"><option value="">— 优点 —</option>{Object.keys(ADVANTAGES_LIBRARY).map((k) => <option key={k} value={k}>{k} ({ADVANTAGES_LIBRARY[k]})</option>)}</select>
          <button onClick={() => { const v = (document.getElementById("adv") as HTMLSelectElement).value; if (!v) return; const [ok, m] = char.addAdvantageByName(v); act(m); }}>获得优点</button>
          <select id="dis"><option value="">— 缺点 —</option>{Object.keys(DISADVANTAGES_LIBRARY).map((k) => <option key={k} value={k}>{k} ({DISADVANTAGES_LIBRARY[k]})</option>)}</select>
          <button onClick={() => { const v = (document.getElementById("dis") as HTMLSelectElement).value; if (!v) return; const [ok, m] = char.addDisadvantageByName(v); act(m); }}>获得缺点</button>
        </div>
        <div className="row" style={{ marginTop: 8 }}>
          <select id="tal"><option value="">— 天赋 —</option>{Object.keys(TALENT_BONUS_GROUPS).map((k) => <option key={k} value={k}>{k}</option>)}</select>
          <select id="tallv" defaultValue="1"><option value="1">Lv.1</option><option value="2">Lv.2</option><option value="3">Lv.3</option></select>
          <button onClick={() => { const v = (document.getElementById("tal") as HTMLSelectElement).value; if (!v) return; const lv = parseInt((document.getElementById("tallv") as HTMLSelectElement).value, 10); const [ok, m] = char.addTalent(v, lv); act(m); }}>获得天赋</button>
        </div>
        <div style={{ marginTop: 8 }}>
          {st.advantages.map((a) => <span className="tag" key={a}>优:{a}</span>)}
          {st.disadvantages.map(([n, r]) => <span className="tag" key={n}>缺:{n}(+{r})</span>)}
          {st.talents.map(([n, l]) => <span className="tag" key={n}>天赋:{n} Lv.{l}</span>)}
        </div>
      </Section>

      <Section title="技能">
        <div className="row">
          <select id="sk"><option value="">— 技能 —</option>{Object.keys(SKILL_LIBRARY).map((k) => <option key={k} value={k}>{k}</option>)}</select>
          <input type="number" id="skr" defaultValue="1" style={{ width: 70 }} />
          <button onClick={() => { const v = (document.getElementById("sk") as HTMLSelectElement).value; if (!v) return; const r = parseInt((document.getElementById("skr") as HTMLInputElement).value, 10); const [ok, m] = char.purchaseSkill(v, r); act(m); }}>购买/提升</button>
        </div>
        <div style={{ marginTop: 8, display: "flex", flexWrap: "wrap", gap: 4 }}>
          {Object.keys(SKILL_LIBRARY).map((k) => {
            const eff = safe(() => char.effectiveSkillRank(k), 0);
            const learned = st.skills[k] || 0;
            return <span className="tag" key={k}>{k}:{learned}{learned > 0 ? `(有效${eff})` : `~${eff}`}</span>;
          })}
        </div>
        {(() => { const miss = char.checkFoundations(); return miss.length ? <div className="hint">⚠ 根基科未投入：{miss.join("、")}</div> : null; })()}
      </Section>

      <Section title="装备">
        <div className="row">
          <select id="eq"><option value="">— 装备 —</option>{Object.keys(EQUIPMENT_LIBRARY).map((k) => <option key={k} value={k}>{k}</option>)}</select>
          <button onClick={() => { const v = (document.getElementById("eq") as HTMLSelectElement).value; if (!v) return; const [ok, m] = char.equipItem(v); act(m); }}>装备</button>
        </div>
        <div style={{ marginTop: 8 }}>
          {st.equipment.map((e) => (
            <span className="tag" key={e} style={{ cursor: "pointer" }} onClick={() => { const [ok, m] = char.unequipItem(e); act(m); }}>✕ {e}</span>
          ))}
        </div>
      </Section>

      <Section title="技术">
        <div className="row">
          <select id="te"><option value="">— 技术 —</option>{Object.keys(TECHNIQUES).map((k) => <option key={k} value={k}>{k}</option>)}</select>
          <button onClick={() => { const v = (document.getElementById("te") as HTMLSelectElement).value; if (!v) return; const [ok, m] = char.purchaseTechnique(v); act(m); }}>学习</button>
        </div>
        <div style={{ marginTop: 8 }}>{st.techniques.map((t) => <span className="tag" key={t}>{t}</span>)}</div>
      </Section>

      <Section title="专长">
        <div className="row">
          <select id="feat-sel"><option value="">— 专长 —</option>{Object.entries(FEATS_LIBRARY).map(([k, v]) => <option key={k} value={k}>{k} ({v.cp}CP)</option>)}</select>
          <select id="feat-choice" defaultValue="">
            <option value="">（选择项）</option>
            <option value="力量">力量</option><option value="敏捷">敏捷</option>
            {ELEMENTS.map((e) => <option key={e} value={e}>{e}</option>)}
          </select>
          <button onClick={() => { const v = (document.getElementById("feat-sel") as HTMLSelectElement).value; if (!v) return; const ch = (document.getElementById("feat-choice") as HTMLSelectElement).value; const [ok, m] = char.addFeat(v, ch); act(m); }}>获得专长</button>
        </div>
        <div style={{ marginTop: 8 }}>{st.feats.map((f) => <span className="tag" key={f}>{f}</span>)}</div>
      </Section>

      <Section title="法术位">
        <div className="row">
          <select id="slot-sel"><option value="">— 环位 —</option>{[1,2,3,4,5,6,7,8,9].map((r) => <option key={r} value={r}>{r} 环（{r}CP，前置奥术施法{2*r-1}）</option>)}</select>
          <button onClick={() => { const v = (document.getElementById("slot-sel") as HTMLSelectElement).value; if (!v) return; const [ok, m] = char.buySlot(parseInt(v, 10)); act(m); }}>购买法术位</button>
        </div>
        <div style={{ marginTop: 8 }}>
          {char.slotTable().length ? char.slotTable().map(([ring, used, owned]) => <span className="tag" key={ring}>{ring}环 {used}/{owned}</span>) : <span className="tag">无法术位</span>}
        </div>
      </Section>

      <Section title="先攻 / 休整">
        <div className="row">
          <button onClick={() => { try { const out = char.rollInitiative(); setLog((l) => [out, ...l].slice(0, 60)); } catch (e: any) { setLog((l) => [`出错: ${e?.message ?? e}`, ...l].slice(0, 60)); } force(); }}>掷先攻</button>
          <button onClick={() => act(char.shortRest())}>短休</button>
          <button onClick={() => act(char.longRest())}>长休</button>
          <input type="number" id="dmg-in" defaultValue="5" style={{ width: 60 }} />
          <button onClick={() => act(char.takeDamage(parseInt((document.getElementById("dmg-in") as HTMLInputElement).value, 10) || 0))}>受伤</button>
          <button onClick={() => act(char.heal(parseInt((document.getElementById("dmg-in") as HTMLInputElement).value, 10) || 0))}>治疗</button>
        </div>
      </Section>

      <Section title="战斗宏">
        <div className="row">
          {MACROS.map(([name, label]) => (
            <button key={name} onClick={() => runMacro(name, label)}>{label}</button>
          ))}
        </div>
        <div className="log" style={{ marginTop: 10 }}>{log[0] ?? "点击上方按钮执行战斗宏…"}</div>
      </Section>

      <Section title="插件（Cordis 服务热挂载）">
        <div className="sub" style={{ marginBottom: 8 }}>web-cordis 风格：在内存中挂载 / 卸载服务。卸载被依赖的服务后，对应能力将报错（演示插件影响范围）。</div>
        {COMPOSITION.map((e) => {
          const on = char.ctx.has(e.id);
          const dep = e.inject.length ? `依赖: ${e.inject.join(",")}` : "无依赖";
          return (
            <div className="plugin" key={e.id}>
              <div>
                <strong>{e.id}</strong>
                <div className="meta">{dep}</div>
              </div>
              <label className="switch">
                <input type="checkbox" checked={on} onChange={(ev) => togglePlugin(e.id, ev.target.checked)} />
                <span className="slider" />
              </label>
            </div>
          );
        })}
        {pluginMsg && <div className="hint">{pluginMsg}</div>}
      </Section>

      <Section title="角色卡">
        <div className="log">{char.showSheet()}</div>
      </Section>
    </div>
  );
}
