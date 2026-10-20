/**
 * d20.web engine/background - 背景系统服务（决策 D：+2 熟练加值；决策 F：仅创建期）
 */
import { Service } from "./core";
import { BACKGROUNDS } from "./data";

export class BackgroundService extends Service {
  static inject: string[] = [];
  BACKGROUNDS = BACKGROUNDS;

  setBackground(name: string): [boolean, string] {
    const st = this.ctx.state;
    if (st.background) return [false, `已选择背景: ${st.background}`];
    if (!(name in this.BACKGROUNDS)) return [false, `未知背景: ${name}`];
    if (st.purchases > 0) return [false, "背景仅可在创建期（未购买任何内容前）选择"];

    const bg = this.BACKGROUNDS[name];
    for (const sk of bg.skills) {
      if (!st.proficiencies.includes(sk)) st.proficiencies.push(sk);
    }
    st.background = name;
    this.ctx.emit("character/changed", "background");
    return [true, `选择背景 ${name}：${bg.skills[0]}、${bg.skills[1]} 熟练 +2`];
  }

  feature(): string {
    const st = this.ctx.state;
    if (!st.background) return "";
    return this.BACKGROUNDS[st.background].feature;
  }
}
