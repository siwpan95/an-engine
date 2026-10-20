/**
 * d20.web engine/rest - 先攻 / 休整服务（决策 E：引入 current_hp）
 */
import { Service } from "./core";
import { abilityMod } from "./data";
import { rollD20, rollD6 } from "./dice";

export class RestService extends Service {
  static inject: string[] = ["derived", "dice", "slots", "feats", "race"];

  currentHp(): number {
    const st = this.ctx.state;
    if (st.currentHp == null) return this.ctx.derived.hp();
    return st.currentHp;
  }

  takeDamage(amount: number, damageType = ""): string {
    const st = this.ctx.state;
    let n = Math.floor(amount);
    if (damageType) {
      const elem = this.ctx.race.elemental();
      const resist =
        (st.race === "提夫林" && damageType === "火") ||
        (this.ctx.race.hasTrait("龙息") && damageType === elem);
      if (resist) n = Math.max(Math.floor(n / 2), 1);
    }
    let newHp = Math.max(this.currentHp() - n, 0);
    let note = "";
    if (newHp === 0 && st.race === "半兽人" && !st.relentlessUsed) {
      st.relentlessUsed = true;
      newHp = 1;
      note = "（濒死不屈：HP 保持 1）";
    }
    st.currentHp = newHp;
    this.ctx.emit("character/changed", "rest");
    return `受到 ${n} 点伤害，HP ${this.currentHp()}/${this.ctx.derived.hp()}${note}`;
  }

  heal(amount: number): string {
    const st = this.ctx.state;
    const n = Math.max(Math.floor(amount), 0);
    st.currentHp = Math.min(this.currentHp() + n, this.ctx.derived.hp());
    this.ctx.emit("character/changed", "rest");
    return `恢复 ${n} 点生命，HP ${this.currentHp()}/${this.ctx.derived.hp()}`;
  }

  initiativeBonus(): number {
    const st = this.ctx.state;
    let base = abilityMod(st.attributes["敏捷"]);
    if (st.advantages.includes("战斗反射")) base += 1;
    return this.ctx.waterfall("derived/initiative", base);
  }

  rollInitiative(): string {
    const bonus = this.initiativeBonus();
    const roll = rollD20();
    return `先攻: d20+${bonus} = ${roll}+${bonus} = ${roll + bonus}`;
  }

  shortRest(): string {
    const st = this.ctx.state;
    const maxHd = st.skills["活力"] || 0;
    if (st.hitDiceUsed >= maxHd) return "无可用生命骰";
    const conMod = abilityMod(st.attributes["体质"]);
    const [, total] = rollD6(1, conMod);
    let healed = total;
    if (st.advantages.includes("快速回复")) healed *= 2;
    if (this.ctx.feats.hasFeat("顽强")) healed = Math.max(healed, 2 * conMod);
    st.hitDiceUsed += 1;
    st.breathUsed = false;
    this.heal(healed);
    return `短休：掷生命骰 1d6+${conMod} 回复 ${healed} 点，HP ${this.currentHp()}/${this.ctx.derived.hp()}，已用生命骰 ${st.hitDiceUsed}/${maxHd}`;
  }

  longRest(): string {
    const st = this.ctx.state;
    st.currentHp = this.ctx.derived.hp();
    const maxHd = st.skills["活力"] || 0;
    st.hitDiceUsed = Math.max(0, st.hitDiceUsed - Math.max(Math.floor(maxHd / 2), 1));
    st.luckyUsed = 0;
    st.breathUsed = false;
    st.relentlessUsed = false;
    this.ctx.slots.recoverAll();
    this.ctx.emit("character/changed", "rest");
    return `长休：HP 回满 ${this.currentHp()}/${this.ctx.derived.hp()}，法术位恢复，生命骰恢复一半（剩余已用 ${st.hitDiceUsed}），每日能力重置`;
  }
}
