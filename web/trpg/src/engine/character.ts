/**
 * d20.web engine/character - Character 公共门面（Cordis 化装配）
 *
 * 9 个子系统挂到 ctx 上的 Service。Character 本身只是一层兼容门面：
 * - 持有 ctx（服务容器 / 事件总线 / 生命周期）与 state（可变实例状态）。
 * - 全部公共方法委托给对应 ctx.<service>.<method>。
 * - 实例状态字段（cp / attributes / skills / ...）通过 Proxy 透明代理到 ctx.state。
 * - 可选 ctx 参数：插件模式下复用宿主 Context（见 index.ts 的 d20Plugin）。
 */
import { Context, ServiceContext } from "./core";
import { loadComposition } from "./loader";
import {
  DEFAULT_STARTING_CP, DEFAULT_MAX_DISADVANTAGE_CP, ATTRIBUTES, EQUIPMENT_LIBRARY,
  SKILL_LIBRARY, DIFFICULTY_COST, TECHNIQUES, TALENT_BONUS_GROUPS, SKILL_CATEGORIES,
  ARMOR_PROFICIENCY, ADVANTAGES_LIBRARY, DISADVANTAGES_LIBRARY, WEAPON_DICE, FINESSE_WEAPONS,
} from "./data";

export class CharacterState {
  cp: number;
  baseCp: number;
  purchases: number;
  maxDisadvantageCp: number;
  attributes: Record<string, number>;
  advantages: string[];
  disadvantages: Array<[string, number]>;
  talents: Array<[string, number]>;
  skills: Record<string, number>;
  techniques: string[];
  armorBonus: number;
  _armorMaxDex: number;
  equipment: string[];
  // ---- 扩充子系统 ----
  race: string;
  raceElement: string;
  background: string;
  feats: string[];
  proficiencies: string[];
  slots: Record<number, number>;
  slotsUsed: Record<number, number>;
  currentHp: number | null;
  hitDiceUsed: number;
  luckyUsed: number;
  breathUsed: boolean;
  relentlessUsed: boolean;

  constructor(startingCp: number, maxDisadvantageCp: number) {
    this.cp = startingCp;
    this.baseCp = startingCp;
    this.purchases = 0;
    this.maxDisadvantageCp = maxDisadvantageCp;
    this.attributes = Object.fromEntries(ATTRIBUTES.map((a) => [a, 10]));
    this.advantages = [];
    this.disadvantages = [];
    this.talents = [];
    this.skills = {};
    this.techniques = [];
    this.armorBonus = 0;
    this._armorMaxDex = 99;
    this.equipment = [];
    this.race = "";
    this.raceElement = "火";
    this.background = "";
    this.feats = [];
    this.proficiencies = [];
    this.slots = {};
    this.slotsUsed = {};
    this.currentHp = null;
    this.hitDiceUsed = 0;
    this.luckyUsed = 0;
    this.breathUsed = false;
    this.relentlessUsed = false;
  }
}

const STATE_ATTRS = [
  "cp", "maxDisadvantageCp", "attributes", "advantages",
  "disadvantages", "talents", "skills", "techniques",
  "equipment", "armorBonus", "_armorMaxDex",
  "race", "raceElement", "background", "feats", "proficiencies",
  "slots", "slotsUsed", "currentHp", "hitDiceUsed",
  "luckyUsed", "breathUsed", "relentlessUsed",
];

export class Character {
  // 类级规则数据（单一事实来源：data），保持 char.SKILL_LIBRARY 等 API
  ATTRIBUTES = ATTRIBUTES;
  EQUIPMENT_LIBRARY = EQUIPMENT_LIBRARY;
  SKILL_LIBRARY = SKILL_LIBRARY;
  DIFFICULTY_COST = DIFFICULTY_COST;
  TECHNIQUES = TECHNIQUES;
  TALENT_BONUS_GROUPS = TALENT_BONUS_GROUPS;
  SKILL_CATEGORIES = SKILL_CATEGORIES;
  ARMOR_PROFICIENCY = ARMOR_PROFICIENCY;
  ADVANTAGES_LIBRARY = ADVANTAGES_LIBRARY;
  DISADVANTAGES_LIBRARY = DISADVANTAGES_LIBRARY;
  WEAPON_DICE = WEAPON_DICE;
  FINESSE_WEAPONS = FINESSE_WEAPONS;
  DEFAULT_STARTING_CP = DEFAULT_STARTING_CP;
  DEFAULT_MAX_DISADVANTAGE_CP = DEFAULT_MAX_DISADVANTAGE_CP;

  ctx: ServiceContext;
  state: CharacterState;

  constructor(
    ctx?: ServiceContext,
    startingCp: number = DEFAULT_STARTING_CP,
    maxDisadvantageCp: number = DEFAULT_MAX_DISADVANTAGE_CP
  ) {
    if (ctx) {
      // 插件模式：复用宿主 Context，由宿主已挂载服务并设好 state
      this.ctx = ctx;
      this.state = ctx.state as CharacterState;
    } else {
      const c = new Context();
      this.ctx = c;
      this.state = new CharacterState(startingCp, maxDisadvantageCp);
      c.state = this.state;
      loadComposition(c);
    }
    return new Proxy(this, {
      get(target: any, prop: string | symbol) {
        if (typeof prop === "symbol") return target[prop];
        if ((STATE_ATTRS as ReadonlyArray<string>).includes(prop as string))
          return target.state[prop];
        return target[prop];
      },
      set(target: any, prop: string | symbol, value: any) {
        if ((STATE_ATTRS as ReadonlyArray<string>).includes(prop as string))
          target.state[prop] = value;
        else target[prop] = value;
        return true;
      },
    });
  }

  // ---- 属性 ----
  setAttribute(attr: string, value: number): [boolean, string] { return this.ctx.attributes.setAttribute(attr, value); }
  attrMod(attr: string): number { return this.ctx.attributes.attrMod(attr); }

  // ---- 优缺点 / 天赋 ----
  addAdvantage(name: string, cost: number): [boolean, string] { return this.ctx.perks.addAdvantage(name, cost); }
  addAdvantageByName(name: string): [boolean, string] { return this.ctx.perks.addAdvantageByName(name); }
  addDisadvantage(name: string, cpReturn: number): [boolean, string] { return this.ctx.perks.addDisadvantage(name, cpReturn); }
  addDisadvantageByName(name: string): [boolean, string] { return this.ctx.perks.addDisadvantageByName(name); }
  addTalent(talentName: string, level = 1): [boolean, string] { return this.ctx.perks.addTalent(talentName, level); }
  getTalentBonus(skillName: string): number { return this.ctx.perks.getTalentBonus(skillName); }

  // ---- 技能 ----
  calcSkillCost(skillName: string, targetRank: number): [number, number] { return this.ctx.skills.calcSkillCost(skillName, targetRank); }
  purchaseSkill(skillName: string, targetRank: number): [boolean, string] { return this.ctx.skills.purchaseSkill(skillName, targetRank); }
  checkFoundations(): string[] { return this.ctx.skills.checkFoundations(); }
  effectiveSkillRank(skillName: string): number { return this.ctx.skills.effectiveSkillRank(skillName); }

  // ---- 技术 ----
  purchaseTechnique(techName: string): [boolean, string] { return this.ctx.techniques.purchaseTechnique(techName); }
  hasTechnique(techName: string): boolean { return this.ctx.techniques.hasTechnique(techName); }

  // ---- 装备 ----
  equipItem(itemName: string): [boolean, string] { return this.ctx.equipment.equipItem(itemName); }
  unequipItem(itemName: string): [boolean, string] { return this.ctx.equipment.unequipItem(itemName); }
  hasFinesseWeapon(): boolean { return this.ctx.equipment.hasFinesseWeapon(); }
  getEquippedWeapon(): string { return this.ctx.equipment.getEquippedWeapon(); }

  // ---- 扩充：种族 / 背景 / 专长 / 法术位 / 休整 ----
  setRace(name: string, choices: Record<string, any> = {}): [boolean, string] { return this.ctx.race.setRace(name, choices); }
  setBackground(name: string): [boolean, string] { return this.ctx.background.setBackground(name); }
  backgroundFeature(): string { return this.ctx.background.feature(); }
  addFeat(name: string, choice = ""): [boolean, string] { return this.ctx.feats.addFeat(name, choice); }
  hasFeat(name: string): boolean { return this.ctx.feats.hasFeat(name); }
  buySlot(ring: number): [boolean, string] { return this.ctx.slots.buySlot(ring); }
  slotTable(): Array<[number, number, number]> { return this.ctx.slots.slotTable(); }
  rollInitiative(): string { return this.ctx.rest.rollInitiative(); }
  shortRest(): string { return this.ctx.rest.shortRest(); }
  longRest(): string { return this.ctx.rest.longRest(); }
  takeDamage(amount: number, damageType = ""): string { return this.ctx.rest.takeDamage(amount, damageType); }
  heal(amount: number): string { return this.ctx.rest.heal(amount); }

  // ---- 衍生数值 ----
  hp(): number { return this.ctx.derived.hp(); }
  attackBonus(melee = true): number { return this.ctx.derived.attackBonus(melee); }
  saveBonus(saveType: string): number { return this.ctx.derived.saveBonus(saveType); }
  get ac(): number { return this.ctx.derived.ac; }
  get maxHp(): number { return this.ctx.derived.maxHp; }

  // ---- 战斗宏 ----
  combatMacro(macroName: string, kwargs: Record<string, any> = {}): string { return this.ctx.combat.combatMacro(macroName, kwargs); }

  // ---- 骰子 ----
  d20Check(skillName: string, dc: number): string { return this.ctx.dice.d20Check(skillName, dc); }
  d100Check(skillName: string): string { return this.ctx.dice.d100Check(skillName); }
  gurpsCheck(skillName: string, modifier = 0): string { return this.ctx.dice.gurpsCheck(skillName, modifier); }
  rollD6(numDice: number, mod = 0): string { return this.ctx.dice.rollD6Str(numDice, mod); }
  rollWeaponDamage(weaponName: string): [number[], string] { return this.ctx.dice.rollWeaponDamageStr(weaponName); }

  // ---- 角色卡 ----
  showSheet(): string { return this.ctx.sheet.showSheet(); }
  toDict(): Record<string, any> { return this.ctx.sheet.toDict(); }

  toString(): string {
    return `<Character CP=${this.state.cp} HP=${this.hp()} AC=${this.ac} skills=${Object.keys(this.state.skills).length} techs=${this.state.techniques.length}>`;
  }
}
