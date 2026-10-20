/**
 * d20.web engine/slots - 法术位系统服务（决策 A：独立 CP 购买环位）
 */
import { Service } from "./core";
import { SPELL_SLOT_CAPS, SPELL_SLOT_TOTAL_CAP, SPELL_SLOT_COST, SPELL_RING_PREREQ } from "./data";

export class SpellSlotsService extends Service {
  static inject: string[] = ["skills"];
  SPELL_SLOT_CAPS = SPELL_SLOT_CAPS;
  SPELL_SLOT_TOTAL_CAP = SPELL_SLOT_TOTAL_CAP;

  buySlot(ring: number): [boolean, string] {
    const st = this.ctx.state;
    if (!(ring in SPELL_SLOT_COST)) return [false, `非法环位: ${ring}（1-9）`];
    const prereq = SPELL_RING_PREREQ[ring];
    const eff = this.ctx.skills.effectiveSkillRank("奥术施法");
    if (eff < prereq) return [false, `需要 奥术施法 有效等级 ≥ ${prereq} 才能购买 ${ring} 环法术位`];
    const cap = this.SPELL_SLOT_CAPS[ring - 1];
    const owned = st.slots[ring] || 0;
    if (owned >= cap) return [false, `${ring} 环法术位已达上限 ${cap}`];
    const total = (Object.values(st.slots) as number[]).reduce((a, b) => a + b, 0);
    if (total >= this.SPELL_SLOT_TOTAL_CAP) return [false, `总法术位已达上限 ${this.SPELL_SLOT_TOTAL_CAP}`];
    const cost = SPELL_SLOT_COST[ring];
    if (st.cp < cost) return [false, `CP不足，需要 ${cost} CP`];
    st.cp -= cost;
    st.slots[ring] = owned + 1;
    st.purchases += 1;
    this.ctx.emit("character/changed", "slots");
    return [true, `购买 ${ring} 环法术位，消耗 ${cost} CP（当前 ${owned + 1}/${cap}）`];
  }

  available(ring: number): number {
    const st = this.ctx.state;
    return (st.slots[ring] || 0) - (st.slotsUsed[ring] || 0);
  }

  spendSlot(ring: number): [boolean, string] {
    if (ring === 0) return [true, "戏法不消耗法术位"];
    if (this.available(ring) <= 0) return [false, `无可用 ${ring} 环法术位`];
    const st = this.ctx.state;
    st.slotsUsed[ring] = (st.slotsUsed[ring] || 0) + 1;
    this.ctx.emit("character/changed", "slots");
    return [true, `消耗 ${ring} 环法术位（剩余 ${this.available(ring)}）`];
  }

  recoverAll(): void {
    this.ctx.state.slotsUsed = {};
  }

  slotTable(): Array<[number, number, number]> {
    const st = this.ctx.state;
    return Object.keys(st.slots).map(Number).sort((a, b) => a - b)
      .map((ring) => [ring, st.slotsUsed[ring] || 0, st.slots[ring]] as [number, number, number]);
  }
}
