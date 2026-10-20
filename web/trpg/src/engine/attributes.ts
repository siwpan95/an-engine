/**
 * d20.web engine/attributes - 属性购买服务
 *
 * 基于 D&D 六属性（凡人均值 10），叠加 GURPS 的递增标价。挂到 ctx.attributes。
 */
import { Service } from "./core";
import { ATTRIBUTES, ATTR_COST_BRACKETS, abilityMod } from "./data";

export function calcAttributeCost(value: number): number {
  if (value < 10) return 0;
  let cost = 0;
  for (let attr = 11; attr <= value; attr++) {
    for (const [low, high, price] of ATTR_COST_BRACKETS) {
      if (low <= attr && attr <= high) {
        cost += price;
        break;
      }
    }
  }
  return cost;
}

export class AttributesService extends Service {
  static inject: string[] = [];
  ATTRIBUTES = ATTRIBUTES;

  calcAttrCost(value: number): number {
    return calcAttributeCost(value);
  }

  setAttribute(attr: string, value: number): [boolean, string] {
    const st = this.ctx.state;
    if (!(attr in st.attributes)) return [false, `未知属性: ${attr}`];
    if (value < 10) return [false, "属性不能低于10"];
    const current = st.attributes[attr];
    const currentCost = calcAttributeCost(current);
    const newCost = calcAttributeCost(value);
    const delta = newCost - currentCost;
    if (st.cp - delta < 0) return [false, `CP不足，需要 ${delta} CP，当前剩余 ${st.cp} CP`];
    st.cp -= delta;
    st.attributes[attr] = value;
    this.ctx.emit("character/changed", "attributes");
    return [true, `${attr} 设置为 ${value}，消耗 ${delta} CP`];
  }

  attrMod(attr: string): number {
    return abilityMod(this.ctx.state.attributes[attr]);
  }
}
