/**
 * d20.web engine/skills - 技能购买与默认值推算服务
 *
 * 技能难度沿用 GURPS 分级（E/A/H/VH），成本按「相对属性等级」查表；默认值（未学习技能
 * 的临时等级）采用 GURPS 的同目/同纲推算思想。挂到 ctx.skills。
 */
import { Service } from "./core";
import { SKILL_LIBRARY, DIFFICULTY_COST, SKILL_CATEGORIES, PROFICIENCY_BONUS } from "./data";

export class SkillsService extends Service {
  static inject: string[] = ["perks", "feats"];
  SKILL_LIBRARY = SKILL_LIBRARY;
  DIFFICULTY_COST = DIFFICULTY_COST;
  SKILL_CATEGORIES = SKILL_CATEGORIES;

  calcSkillCost(skillName: string, targetRank: number): [number, number] {
    if (!(skillName in this.SKILL_LIBRARY)) return [0, 0];
    const [attrName, diff] = this.SKILL_LIBRARY[skillName];
    const attrVal = this.ctx.state.attributes[attrName];
    const currentRank = this.ctx.state.skills[skillName] || 0;
    if (targetRank <= currentRank) return [0, 0];

    let totalCost = 0;
    const costTable = this.DIFFICULTY_COST[diff];
    const extraCost = costTable.extra as number;
    const numericKeys = Object.keys(costTable)
      .filter((k) => k !== "extra")
      .map((k) => parseInt(k, 10));
    const maxKey = numericKeys.length ? Math.max(...numericKeys) : 0;

    for (let rank = currentRank; rank < targetRank; rank++) {
      const rel = rank - attrVal;
      const relKey = String(rel);
      if (relKey in costTable) {
        totalCost += costTable[relKey as keyof typeof costTable] as number;
      } else if (rel > maxKey) {
        const base = costTable[maxKey as keyof typeof costTable] as number;
        totalCost += base + extraCost * (rel - maxKey);
      } else {
        totalCost += 1;
      }
    }
    return [totalCost, targetRank - currentRank];
  }

  purchaseSkill(skillName: string, targetRank: number): [boolean, string] {
    if (!(skillName in this.SKILL_LIBRARY)) return [false, "未知技能"];
    const [cost] = this.calcSkillCost(skillName, targetRank);
    if (cost === 0) return [false, "目标等级未提高"];
    const st = this.ctx.state;
    if (st.cp < cost) return [false, `CP不足，需要 ${cost} CP，当前剩余 ${st.cp} CP`];
    st.cp -= cost;
    st.skills[skillName] = targetRank;
    this.ctx.emit("character/changed", "skills");
    return [true, `${skillName} 提升至 ${targetRank}，消耗 ${cost} CP`];
  }

  checkFoundations(): string[] {
    const st = this.ctx.state;
    const missing: string[] = [];
    for (const [name, [, , isFound]] of Object.entries(this.SKILL_LIBRARY)) {
      if (isFound && (st.skills[name] || 0) < 1) missing.push(name);
    }
    return missing;
  }

  effectiveSkillRank(skillName: string): number {
    const st = this.ctx.state;
    const learned = st.skills[skillName] || 0;
    let base: number;
    if (learned > 0) {
      base = learned + (this.ctx as any).perks.getTalentBonus(skillName);
    } else if (!(skillName in this.SKILL_LIBRARY)) {
      base = 0;
    } else {
      const [attrName] = this.SKILL_LIBRARY[skillName];
      const sameAttrRanks = Object.entries(this.SKILL_LIBRARY)
        .filter(([s, [a]]) => a === attrName && (st.skills[s] || 0) > 0 && s !== skillName)
        .map(([s]) => st.skills[s]);
      if (sameAttrRanks.length) {
        base = Math.max(Math.floor(sameAttrRanks.reduce((x, y) => x + y, 0) / sameAttrRanks.length) - 2, 0);
      } else {
        base = 0;
        for (const [, skills] of Object.entries(this.SKILL_CATEGORIES)) {
          if (skills.includes(skillName)) {
            const catRanks = skills
              .filter((s) => (st.skills[s] || 0) > 0 && s !== skillName)
              .map((s) => st.skills[s]);
            if (catRanks.length)
              base = Math.max(Math.floor(catRanks.reduce((x, y) => x + y, 0) / catRanks.length) - 3, 0);
            break;
          }
        }
      }
    }
    // 熟练（背景/种族）+2 与专长技能加值
    if (st.proficiencies.includes(skillName)) base += PROFICIENCY_BONUS;
    base += (this.ctx as any).feats.skillBonus(skillName);
    return base;
  }
}
