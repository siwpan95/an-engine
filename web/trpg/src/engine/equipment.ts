/**
 * d20.web engine/equipment - 装备系统服务
 *
 * D&D 5e 风格的武器/护甲/盾牌库。装备护甲/盾牌需满足熟练度（技能）要求并消耗 CP；
 * 护甲提供 AC 加值与最大敏捷上限。挂到 ctx.equipment。
 */
import { Service } from "./core";
import { EQUIPMENT_LIBRARY, ARMOR_PROFICIENCY, FINESSE_WEAPONS } from "./data";

export class EquipmentService extends Service {
  static inject: string[] = [];
  EQUIPMENT_LIBRARY = EQUIPMENT_LIBRARY;
  ARMOR_PROFICIENCY = ARMOR_PROFICIENCY;
  FINESSE_WEAPONS = FINESSE_WEAPONS;

  equipItem(itemName: string): [boolean, string] {
    const st = this.ctx.state;
    if (!(itemName in this.EQUIPMENT_LIBRARY)) return [false, "未知装备"];
    const [etype, sub, , , , , cpCost] = this.EQUIPMENT_LIBRARY[itemName];

    if (etype === "护甲" || etype === "盾牌") {
      // 山地矮人特性「免中甲熟练」：中甲无需近战攻击技能
      if (st.race === "山地矮人" && sub === "中甲") {
        /* 免中甲熟练 */
      } else {
        const reqSkill = this.ARMOR_PROFICIENCY[sub];
        if (reqSkill && (st.skills[reqSkill] || 0) < 1)
          return [false, `需要 ${reqSkill} 至少1级才能装备${sub}`];
      }
    }
    if (st.cp < cpCost) return [false, `CP不足，需要 ${cpCost} CP`];

    st.cp -= cpCost;
    st.equipment.push(itemName);
    st.purchases += 1;
    this.recalcArmorBonus();
    this.ctx.emit("character/changed", "equipment");
    return [true, `装备了 ${itemName}，消耗 ${cpCost} CP`];
  }

  unequipItem(itemName: string): [boolean, string] {
    const st = this.ctx.state;
    if (!st.equipment.includes(itemName)) return [false, "未装备此物品"];
    st.equipment = st.equipment.filter((x: string) => x !== itemName);
    const cpCost = this.EQUIPMENT_LIBRARY[itemName][6];
    st.cp += cpCost;
    this.recalcArmorBonus();
    return [true, `卸下了 ${itemName}，返还 ${cpCost} CP`];
  }

  recalcArmorBonus(): void {
    const st = this.ctx.state;
    let totalArmor = 0;
    let bestMaxDex = 99;
    for (const item of st.equipment) {
      const info = this.EQUIPMENT_LIBRARY[item];
      if (info && (info[0] === "护甲" || info[0] === "盾牌")) {
        totalArmor += info[2];
        if (info[3] < bestMaxDex) bestMaxDex = info[3];
      }
    }
    st.armorBonus = totalArmor;
    st._armorMaxDex = bestMaxDex;
  }

  getEquippedWeapon(): string {
    const st = this.ctx.state;
    for (const item of st.equipment) {
      const info = this.EQUIPMENT_LIBRARY[item];
      if (info && info[0] === "武器") return item;
    }
    return "徒手";
  }

  hasFinesseWeapon(): boolean {
    const st = this.ctx.state;
    return st.equipment.some(
      (w: string) => this.FINESSE_WEAPONS.has(w) && this.EQUIPMENT_LIBRARY[w]?.[0] === "武器"
    );
  }
}
