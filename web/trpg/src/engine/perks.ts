/**
 * d20.web engine/perks - 优点 / 缺点 / 天赋服务
 *
 * 参考 GURPS 的优点（Advantages）、缺点（Disadvantages，返还 CP，上限为起始 CP 一半）
 * 与天赋（Talent，对一组相关技能提供加成）。挂到 ctx.perks。
 */
import { Service } from "./core";
import { ADVANTAGES_LIBRARY, DISADVANTAGES_LIBRARY, TALENT_BONUS_GROUPS } from "./data";

export class PerksService extends Service {
  static inject: string[] = [];
  ADVANTAGES_LIBRARY = ADVANTAGES_LIBRARY;
  DISADVANTAGES_LIBRARY = DISADVANTAGES_LIBRARY;
  TALENT_BONUS_GROUPS = TALENT_BONUS_GROUPS;

  // ---------- 优点 ----------
  addAdvantage(name: string, cost: number): [boolean, string] {
    const st = this.ctx.state;
    if (st.cp < cost) return [false, "CP不足"];
    st.advantages.push(name);
    st.cp -= cost;
    return [true, `获得优点：${name}，消耗 ${cost} CP`];
  }

  addAdvantageByName(name: string): [boolean, string] {
    if (!(name in this.ADVANTAGES_LIBRARY)) return [false, `未知优点: ${name}`];
    return this.addAdvantage(name, this.ADVANTAGES_LIBRARY[name]);
  }

  // ---------- 缺点 ----------
  addDisadvantage(name: string, cpReturn: number): [boolean, string] {
    const st = this.ctx.state;
    const totalReturned = st.disadvantages.reduce((s: number, [, r]: [string, number]) => s + r, 0);
    if (totalReturned + cpReturn > st.maxDisadvantageCp)
      return [false, `缺点返还CP不能超过${st.maxDisadvantageCp}`];
    st.disadvantages.push([name, cpReturn]);
    st.cp += cpReturn;
    return [true, `获得缺点：${name}，返还 ${cpReturn} CP`];
  }

  addDisadvantageByName(name: string): [boolean, string] {
    if (!(name in this.DISADVANTAGES_LIBRARY)) return [false, `未知缺点: ${name}`];
    return this.addDisadvantage(name, this.DISADVANTAGES_LIBRARY[name]);
  }

  // ---------- 天赋 ----------
  addTalent(talentName: string, level = 1): [boolean, string] {
    const st = this.ctx.state;
    if (!(talentName in this.TALENT_BONUS_GROUPS)) return [false, `未知天赋: ${talentName}`];
    if (!(1 <= level && level <= 3)) return [false, "天赋等级需在 1-3 之间"];
    const cost = 5 * level;
    if (st.cp < cost) return [false, "CP不足"];
    st.talents.push([talentName, level]);
    st.cp -= cost;
    return [true, `获得天赋 ${talentName} Lv.${level}，消耗 ${cost} CP`];
  }

  getTalentBonus(skillName: string): number {
    const st = this.ctx.state;
    let bonus = 0;
    for (const [talentName, level] of st.talents) {
      const group = this.TALENT_BONUS_GROUPS[talentName] || [];
      if (group.includes(skillName)) bonus += level;
    }
    return bonus;
  }
}
