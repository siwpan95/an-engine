/**
 * d20.web engine/race - 种族系统服务（决策 C：GURPS 式模板定价；决策 F：仅创建期）
 */
import { Service } from "./core";
import { RACE_TEMPLATES, HALF_ELF_DEFAULT_PICKS, ATTRIBUTES } from "./data";
import { rollD20 } from "./dice";

export class RaceService extends Service {
  static inject: string[] = [];
  RACE_TEMPLATES = RACE_TEMPLATES;
  private _disposers: Array<() => void> = [];

  apply(): void {
    this._disposers = [
      this.ctx.on("derived/max_hp", (hp: number, nxt: (v: any) => any) =>
        this.hasTrait("HP+活力等级") ? nxt(hp + (this.ctx.state.skills["活力"] || 0)) : nxt(hp)),
      this.ctx.on("derived/initiative", (b: number, nxt: (v: any) => any) =>
        this.hasTrait("先攻+1") ? nxt(b + 1) : nxt(b)),
      this.ctx.on("dice/d20_roll", (r: number, nxt: (v: any) => any) =>
        r === 1 && this.hasTrait("幸运重掷") ? nxt(rollD20()) : nxt(r)),
    ];
  }

  dispose(): void {
    for (const d of this._disposers) d();
  }

  setRace(name: string, choices: Record<string, any> = {}): [boolean, string] {
    const st = this.ctx.state;
    if (st.race) return [false, `已选择种族: ${st.race}`];
    if (!(name in this.RACE_TEMPLATES)) return [false, `未知种族: ${name}`];
    if (st.purchases > 0) return [false, "种族仅可在创建期（未购买任何内容前）选择"];

    const tpl = this.RACE_TEMPLATES[name];
    if (st.cp < tpl.cp) return [false, `CP不足，${name} 模板价格 ${tpl.cp} CP`];
    st.cp -= tpl.cp;
    for (const [attr, bonus] of Object.entries(tpl.bonuses)) {
      st.attributes[attr] = Math.min(10 + bonus, 20);
    }
    const choose = tpl.choose || {};
    if ("任选+1" in choose) {
      const picks = choices["任选+1"] || HALF_ELF_DEFAULT_PICKS;
      for (const attr of picks.slice(0, 2)) {
        if (ATTRIBUTES.includes(attr)) st.attributes[attr] = Math.min(st.attributes[attr] + 1, 20);
      }
    }
    if ("元素" in choose) st.raceElement = choices["元素"] || "火";
    st.advantages.push(...tpl.advantages);
    for (const sk of tpl.proficiencies) {
      if (!st.proficiencies.includes(sk)) st.proficiencies.push(sk);
    }
    if (tpl.traits.includes("免费戏法") && !st.techniques.includes("火焰箭")) st.techniques.push("火焰箭");
    st.race = name;
    this.ctx.emit("character/changed", "race");
    return [true, `选择种族 ${name}，消耗 ${tpl.cp} CP`];
  }

  template(name?: string): RaceTemplateLike | undefined {
    return this.RACE_TEMPLATES[name || this.ctx.state.race];
  }

  hasTrait(trait: string): boolean {
    const tpl = this.template();
    return Boolean(tpl && tpl.traits.includes(trait));
  }

  saveBonusAdjust(saveType: string): number {
    if (saveType === "fort" && this.hasTrait("强韧豁免+2")) return 2;
    if (saveType === "will" && this.hasTrait("意志豁免+2")) return 2;
    return 0;
  }

  elemental(): string {
    if (this.ctx.state.race === "提夫林") return "火";
    return this.ctx.state.raceElement || "火";
  }
}

type RaceTemplateLike = { cp: number; traits: string[] };
