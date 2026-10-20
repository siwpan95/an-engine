/**
 * d20.web engine/feats - 专长系统服务（决策 B：8/12/15 CP 分档）
 *
 * 效果经事件钩子（waterfall）挂到 derived 等计算链；卸载本服务后加成随之消失。
 */
import { Service } from "./core";
import { FEATS_LIBRARY, ELEMENTS } from "./data";

export class FeatsService extends Service {
  static inject: string[] = [];
  FEATS_LIBRARY = FEATS_LIBRARY;
  ELEMENTS = ELEMENTS;
  private _disposers: Array<() => void> = [];

  apply(): void {
    this._disposers = [
      this.ctx.on("derived/max_hp", (hp: number, nxt: (v: any) => any) =>
        this.hasFeat("强壮") ? nxt(hp + 2 * (this.ctx.state.skills["活力"] || 0)) : nxt(hp)),
      this.ctx.on("derived/initiative", (b: number, nxt: (v: any) => any) =>
        this.hasFeat("警觉") ? nxt(b + 5) : nxt(b)),
    ];
  }

  dispose(): void {
    for (const d of this._disposers) d();
  }

  addFeat(name: string, choice = ""): [boolean, string] {
    const st = this.ctx.state;
    if (!(name in this.FEATS_LIBRARY)) return [false, `未知专长: ${name}`];
    if (this.hasFeat(name)) return [false, "已拥有此专长"];
    const info = this.FEATS_LIBRARY[name];
    const [ok, msg] = this.checkPrereq(info.prereq);
    if (!ok) return [false, msg];
    if (name === "元素亲和" && !this.ELEMENTS.includes(choice))
      return [false, `元素亲和需指定元素: ${this.ELEMENTS.join("/")}`];
    if (name === "运动员" && !(choice === "力量" || choice === "敏捷"))
      return [false, "运动员需指定 力量 或 敏捷"];
    if (st.cp < info.cp) return [false, `CP不足，需要 ${info.cp} CP`];
    st.cp -= info.cp;
    const label = choice ? `${name}(${choice})` : name;
    st.feats.push(label);
    st.purchases += 1;
    this.applyImmediate(name, choice);
    this.ctx.emit("character/changed", "feats");
    return [true, `获得专长 ${label}，消耗 ${info.cp} CP`];
  }

  private checkPrereq(prereq: Record<string, any>): [boolean, string] {
    const st = this.ctx.state;
    for (const [attr, minVal] of Object.entries((prereq.attr || {}) as Record<string, number>)) {
      if ((st.attributes[attr] || 0) < (minVal as number)) return [false, `需要 ${attr} ≥ ${minVal}`];
    }
    for (const [skill, minRank] of prereq.skills || []) {
      if ((st.skills[skill] || 0) < minRank) return [false, `需要 ${skill} ≥ ${minRank} 级`];
    }
    if (prereq.spellcasting) {
      if ((st.skills["奥术施法"] || 0) < 1 && (st.skills["施法攻击"] || 0) < 1)
        return [false, "需要会施法（奥术施法或施法攻击 ≥1 级）"];
    }
    return [true, ""];
  }

  private applyImmediate(name: string, choice: string): void {
    const st = this.ctx.state;
    if (name === "运动员" && choice) st.attributes[choice] = Math.min(st.attributes[choice] + 1, 20);
    else if (name === "演员") st.attributes["魅力"] = Math.min(st.attributes["魅力"] + 1, 20);
    else if (name === "顽强") st.attributes["体质"] = Math.min(st.attributes["体质"] + 1, 20);
  }

  hasFeat(name: string): boolean {
    return this.ctx.state.feats.some((f: string) => f === name || f.startsWith(name + "("));
  }

  skillBonus(skillName: string): number {
    let bonus = 0;
    if (this.hasFeat("演员") && (skillName === "欺瞒" || skillName === "表演")) bonus += 2;
    if (this.hasFeat("观察力") && (skillName === "侦察" || skillName === "调查")) bonus += 2;
    return bonus;
  }

  elementPicked(): string {
    for (const f of this.ctx.state.feats as string[]) {
      if (f.startsWith("元素亲和(")) return f.slice("元素亲和(".length, -1);
    }
    return "";
  }
}
