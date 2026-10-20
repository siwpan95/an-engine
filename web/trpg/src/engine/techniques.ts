/**
 * d20.web engine/techniques - 技术（战技/法术）购买服务
 *
 * 融合 D&D 的战技/法术与 GURPS 的 Technique（买除惩罚）。挂到 ctx.techniques。
 */
import { Service } from "./core";
import { TECHNIQUES } from "./data";

export class TechniquesService extends Service {
  static inject: string[] = [];
  TECHNIQUES = TECHNIQUES;

  purchaseTechnique(techName: string): [boolean, string] {
    const st = this.ctx.state;
    if (!(techName in this.TECHNIQUES)) return [false, `未知技术: ${techName}`];
    if (st.techniques.includes(techName)) return [false, "已拥有此技术"];
    const [reqSkill, reqRank, attrReq, , cost] = this.TECHNIQUES[techName];
    const currentRank = st.skills[reqSkill] || 0;
    if (currentRank < reqRank) return [false, `需要 ${reqSkill} 至少 ${reqRank} 级`];
    for (const [attr, minVal] of Object.entries(attrReq)) {
      if (st.attributes[attr] < (minVal as number)) return [false, `需要 ${attr} ${minVal}`];
    }
    if (st.cp < cost) return [false, "CP不足"];
    st.cp -= cost;
    st.techniques.push(techName);
    this.ctx.emit("character/changed", "techniques");
    return [true, `学会技术 ${techName}，消耗 ${cost} CP`];
  }

  hasTechnique(techName: string): boolean {
    return this.ctx.state.techniques.includes(techName);
  }
}
