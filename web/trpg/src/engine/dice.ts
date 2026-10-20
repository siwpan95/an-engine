/**
 * d20.web engine/dice - 骰子系统（纯函数 + DiceService）
 *
 * 融合 D&D 的 d20/d100/d6 与 GURPS 的 3d6 roll-low 检定。纯函数便于测试；DiceService
 * 挂到 ctx.dice 提供实例方法。
 */
import { Service } from "./core";
import { WEAPON_DICE } from "./data";

// -----------------------------------------------------------------------------
//  纯函数
// -----------------------------------------------------------------------------
export function rollD20(): number {
  return Math.floor(Math.random() * 20) + 1;
}

export function rollD100(): number {
  return Math.floor(Math.random() * 100) + 1;
}

export function rollD6(num: number, mod = 0): [number[], number] {
  const rolls = Array.from({ length: num }, () => Math.floor(Math.random() * 6) + 1);
  return [rolls, rolls.reduce((a, b) => a + b, 0) + mod];
}

export function roll3d6(): [number[], number] {
  const rolls = Array.from({ length: 3 }, () => Math.floor(Math.random() * 6) + 1);
  return [rolls, rolls.reduce((a, b) => a + b, 0)];
}

export function gurpsSuccessChance(skillLevel: number): number {
  const table: Record<number, number> = {
    3: 0.5, 4: 2, 5: 5, 6: 9, 7: 16, 8: 26, 9: 38, 10: 50,
    11: 63, 12: 74, 13: 84, 14: 90, 15: 95, 16: 98, 17: 98, 18: 100,
  };
  if (skillLevel <= 3) return 0;
  if (skillLevel >= 18) return 100;
  return Math.round(table[skillLevel] ?? 50);
}

export function rollWeaponDamage(weaponName: string): [number[], string] {
  const [num, die] = WEAPON_DICE[weaponName] || [1, 4];
  const rolls = Array.from({ length: num }, () => Math.floor(Math.random() * die) + 1);
  return [rolls, `${num}d${die}`];
}

// -----------------------------------------------------------------------------
//  DiceService
// -----------------------------------------------------------------------------
export class DiceService extends Service {
  static inject: string[] = ["skills", "feats"];

  /** 掷 d20 并应用钩子：半身人幸运（掷 1 重掷）、专长幸运（每日 3 次重掷取高）。 */
  d20Roll(): number {
    let roll = this.ctx.waterfall("dice/d20_roll", rollD20());
    const st = this.ctx.state;
    if ((this.ctx as any).feats.hasFeat("幸运") && st.luckyUsed < 3) {
      roll = Math.max(roll, rollD20());
      st.luckyUsed += 1;
    }
    return roll;
  }

  d20Check(skillName: string, dc: number): string {
    const rank = (this.ctx as any).skills.effectiveSkillRank(skillName);
    const isDefault = (this.ctx.state.skills[skillName] || 0) === 0;
    const roll = this.d20Roll();
    const result = roll + rank;
    const success = result >= dc;
    const defaultTag = isDefault ? " [默认值]" : "";
    return `d20+${rank}${defaultTag} = ${roll}+${rank} = ${result} vs DC ${dc} ${success ? "成功" : "失败"}`;
  }

  d100Check(skillName: string): string {
    const rank = (this.ctx as any).skills.effectiveSkillRank(skillName);
    const isDefault = (this.ctx.state.skills[skillName] || 0) === 0;
    const target = rank * 5;
    const roll = rollD100();
    const success = roll <= target;
    const defaultTag = isDefault ? " [默认值]" : "";
    return `成功率 ${target}%${defaultTag}，掷出 ${roll} ${success ? "成功" : "失败"}`;
  }

  gurpsCheck(skillName: string, modifier = 0): string {
    const rank = (this.ctx as any).skills.effectiveSkillRank(skillName);
    const target = rank + modifier;
    const [rolls, total] = roll3d6();
    let outcome: string;
    if (total <= 4 || (total === 5 && target >= 15) || (total === 6 && target >= 16)) outcome = "大成功！";
    else if (total >= 17 || (total === 17 && target <= 15)) outcome = total === 18 || (total === 17 && target <= 15) ? "大失败！" : "失败";
    else outcome = total <= target ? "成功" : "失败";
    const modStr = modifier ? `${modifier >= 0 ? "+" : ""}${modifier}` : "0";
    return `3d6(${rolls}=${total}) vs ${rank}[${modStr}]=${target} → ${outcome}`;
  }

  rollD6Str(numDice: number, mod = 0): string {
    const [rolls, total] = rollD6(numDice, mod);
    return `${numDice}d6+${mod} = ${rolls} = ${total}`;
  }

  rollWeaponDamageStr(weaponName: string): [number[], string] {
    return rollWeaponDamage(weaponName);
  }
}
