/**
 * d20.web engine/derived - 衍生数值服务
 *
 * 由属性、技能、装备、天赋推算出的战斗数值：HP、AC、攻击加值、豁免加值。挂到 ctx.derived。
 */
import { Service } from "./core";
import { abilityMod } from "./data";

export class DerivedService extends Service {
  static inject: string[] = ["skills", "equipment", "feats", "race"];

  get maxHp(): number {
    const st = this.ctx.state;
    const conMod = abilityMod(st.attributes["体质"]);
    const vitRank = st.skills["活力"] || 0;
    if (vitRank === 0) return 0;
    const base = 6 + conMod + (vitRank - 1) * (3.5 + conMod);
    return this.ctx.waterfall("derived/max_hp", base);
  }

  hp(): number {
    const m = this.maxHp;
    return m ? Math.floor(m) : 0;
  }

  get ac(): number {
    const st = this.ctx.state;
    const dexMod = abilityMod(st.attributes["敏捷"]);
    const maxDex = st._armorMaxDex ?? 99;
    const effectiveDex = Math.min(dexMod, maxDex);
    const dodgeRank = st.skills["闪避防御"] || 0;
    const dodgeBonus = Math.floor(dodgeRank / 2);
    let ac = 10 + effectiveDex + dodgeBonus + st.armorBonus;
    // 双持大师：双持两把近战武器 +1
    const weapons = st.equipment.filter((e: string) => {
      const info = this.ctx.equipment.EQUIPMENT_LIBRARY[e];
      return info && info[0] === "武器" && ["近战", "近战-轻", "近战-双手"].includes(info[1]);
    });
    if (this.ctx.feats.hasFeat("双持大师") && weapons.length >= 2) ac += 1;
    // 防御决斗者：装备灵巧武器 +2
    if (this.ctx.feats.hasFeat("防御决斗者") && this.ctx.equipment.hasFinesseWeapon()) ac += 2;
    return ac;
  }

  attackBonus(melee = true): number {
    const skill = melee ? "近战攻击" : "远程攻击";
    return (this.ctx as any).skills.effectiveSkillRank(skill);
  }

  saveBonus(saveType: string): number {
    const mapping: Record<string, [string, string]> = {
      fort: ["强韧豁免", "体质"],
      ref: ["反射豁免", "敏捷"],
      will: ["意志豁免", "感知"],
    };
    if (!(saveType in mapping)) throw new Error(`未知豁免类型: ${saveType}`);
    const [skill, attr] = mapping[saveType];
    const rank = (this.ctx as any).skills.effectiveSkillRank(skill);
    const mod = abilityMod(this.ctx.state.attributes[attr]);
    return rank + mod + this.ctx.race.saveBonusAdjust(saveType);
  }
}
