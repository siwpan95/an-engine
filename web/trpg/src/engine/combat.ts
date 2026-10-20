/**
 * d20.web engine/combat - 战斗宏服务
 *
 * 融合 D&D 的战技/法术与 GURPS 的战斗机动（Maneuver）。所有宏返回可读字符串。挂到
 * ctx.combat。法术宏经 ctx.slots 消耗法术位并支持上环施法（upcast）；战斗骰经
 * ctx.dice.d20Roll() 统一入口（幸运/半身人重掷钩子生效）。
 */
import { Service } from "./core";
import { TECHNIQUES, SPELL_RINGS } from "./data";

const rand = (n: number) => Math.floor(Math.random() * n) + 1;

export class CombatService extends Service {
  static inject: string[] = ["derived", "equipment", "dice", "techniques", "skills", "slots", "feats", "rest"];
  TECHNIQUES = TECHNIQUES;

  combatMacro(macroName: string, kwargs: Record<string, any> = {}): string {
    const macros: Record<string, (k?: any) => string> = {
      melee_attack: (k) => this.macroMeleeAttack(k),
      ranged_attack: (k) => this.macroRangedAttack(k),
      sneak_attack: (k) => this.macroSneakAttack(k),
      power_attack: (k) => this.macroPowerAttack(k),
      whirlwind: (k) => this.macroWhirlwind(k),
      fireball: (k) => this.macroFireball(k),
      magic_missile: (k) => this.macroMagicMissile(k),
      healing_word: (k) => this.macroHealingWord(k),
      fire_bolt: (k) => this.macroFireBolt(k),
      ray_of_frost: (k) => this.macroRayOfFrost(k),
      scorching_ray: (k) => this.macroScorchingRay(k),
      lightning_bolt: (k) => this.macroLightningBolt(k),
      cone_of_cold: (k) => this.macroConeOfCold(k),
      meteor_swarm: (k) => this.macroMeteorSwarm(k),
      dragon_breath: (k) => this.macroDragonBreath(),
      deceptive_attack: (k) => this.macroDeceptiveAttack(k),
      rapid_strike: (k) => this.macroRapidStrike(k),
      allout_strong: (k) => this.macroAlloutStrong(k),
      allout_determined: (k) => this.macroAlloutDetermined(k),
    };
    const handler = macros[macroName];
    if (!handler) return `未知战斗宏: ${macroName}`;
    return handler(kwargs);
  }

  // ====================================================================
  //  辅助
  // ====================================================================
  private dmgRolls(num: number, die: number, element = ""): number[] {
    let rolls = Array.from({ length: num }, () => rand(die));
    if (element && this.ctx.feats.elementPicked() === element) {
      rolls = rolls.map((r) => (r === 1 ? 2 : r));
    }
    return rolls;
  }

  private strMod(): number {
    return Math.max(Math.floor((this.ctx.state.attributes["力量"] - 10) / 2), 0);
  }

  private weaponHit(weapon: string, strMod: number): string {
    const [dmgRolls, dmgDesc] = this.ctx.dice.rollWeaponDamageStr(weapon);
    const total = dmgRolls.reduce((a: number, b: number) => a + b, 0) + strMod;
    return `  ✓ 命中！伤害: ${dmgDesc}+${strMod} = ${total}`;
  }

  private spend(ring: number): [boolean, string] {
    return this.ctx.slots.spendSlot(ring);
  }

  // ====================================================================
  //  D&D 风格战技 / 法术
  // ====================================================================
  private macroMeleeAttack(k: any = {}): string {
    const atkBonus = this.ctx.derived.attackBonus(true);
    const penalty = k.gwm && this.ctx.feats.hasFeat("巨武宗师") ? -5 : 0;
    const bonusDmg = penalty ? 10 : 0;
    const roll = this.ctx.dice.d20Roll();
    const total = roll + atkBonus + penalty;
    const targetAc = k.targetAc ?? 10;
    const hit = total >= targetAc;
    const tag = penalty ? " [巨武宗师]" : "";
    const lines = [`⚔ 近战攻击: d20+${atkBonus}${penalty}${tag} = ${roll}+${atkBonus + penalty} = ${total} vs AC ${targetAc}`];
    if (hit) {
      const weapon = this.ctx.equipment.getEquippedWeapon();
      const [dmgRolls, dmgDesc] = this.ctx.dice.rollWeaponDamageStr(weapon);
      const totalDmg = dmgRolls.reduce((a: number, b: number) => a + b, 0) + this.strMod() + bonusDmg;
      lines.push(`  ✓ 命中！伤害: ${dmgDesc}+${this.strMod()}(力量)` +
        (bonusDmg ? `+${bonusDmg}(巨武)` : "") + ` = ${totalDmg}`);
    } else lines.push("  ✗ 未命中");
    return lines.join("\n");
  }

  private macroRangedAttack(k: any = {}): string {
    const atkBonus = this.ctx.derived.attackBonus(false);
    const penalty = k.sharpshooter && this.ctx.feats.hasFeat("神射手") ? -5 : 0;
    const bonusDmg = penalty ? 10 : 0;
    const roll = this.ctx.dice.d20Roll();
    const total = roll + atkBonus + penalty;
    const targetAc = k.targetAc ?? 10;
    const tag = penalty ? " [神射手]" : "";
    const lines = [`🏹 远程攻击: d20+${atkBonus}${penalty}${tag} = ${roll}+${atkBonus + penalty} = ${total} vs AC ${targetAc}`];
    if (total >= targetAc) {
      const weapon = this.ctx.equipment.getEquippedWeapon();
      const [dmgRolls, dmgDesc] = this.ctx.dice.rollWeaponDamageStr(weapon);
      const totalDmg = dmgRolls.reduce((a: number, b: number) => a + b, 0) + bonusDmg;
      lines.push(`  ✓ 命中！伤害: ${dmgDesc}` + (bonusDmg ? `+${bonusDmg}(神射)` : "") + ` = ${totalDmg}`);
    } else lines.push("  ✗ 未命中");
    return lines.join("\n");
  }

  private sneakAttackDice(): number {
    if (!this.ctx.equipment.hasFinesseWeapon()) return 0;
    const rank = this.ctx.derived.attackBonus(true);
    const dice = Math.max(0, Math.floor((rank - 4) / 2) + 1);
    return Math.min(dice, 10);
  }

  private macroSneakAttack(k: any = {}): string {
    const atkBonus = this.ctx.derived.attackBonus(true);
    const roll = this.ctx.dice.d20Roll();
    const total = roll + atkBonus;
    const targetAc = k.targetAc ?? 10;
    const hasTech = this.ctx.techniques.hasTechnique("偷袭要害打击");
    const lines = [`🗡 偷袭攻击: d20+${atkBonus} = ${roll}+${atkBonus} = ${total} vs AC ${targetAc}`];
    let hit = total >= targetAc;
    if (hasTech) {
      const penalty = this.TECHNIQUES["偷袭要害打击"][3];
      if (penalty) lines.push(`  技术修正: 攻击${penalty}`);
      const adjusted = total + penalty;
      hit = adjusted >= targetAc;
      lines.push(`  调整后: ${adjusted} vs AC ${targetAc}`);
    }
    if (hit) {
      const weapon = this.ctx.equipment.getEquippedWeapon();
      const [dmgRolls, dmgDesc] = this.ctx.dice.rollWeaponDamageStr(weapon);
      const totalDmg = dmgRolls.reduce((a: number, b: number) => a + b, 0) + this.strMod();
      lines.push(`  ✓ 命中！基础伤害: ${dmgDesc}+${this.strMod()}(力量) = ${dmgRolls}+${this.strMod()} = ${totalDmg}`);
      if (hasTech && (k.flatFooted ?? true)) {
        const dice = this.sneakAttackDice();
        if (dice > 0) {
          const sneak = Array.from({ length: dice }, () => rand(6));
          lines.push(`  💀 偷袭精准伤害: ${dice}d6 = ${sneak} = ${sneak.reduce((a: number, b: number) => a + b, 0)}`);
          lines.push(`  总伤害: ${totalDmg + sneak.reduce((a: number, b: number) => a + b, 0)}`);
        }
      }
    } else lines.push("  ✗ 未命中");
    return lines.join("\n");
  }

  private macroPowerAttack(k: any = {}): string {
    if (!this.ctx.techniques.hasTechnique("猛力攻击")) return "未学会「猛力攻击」技术";
    const atkBonus = this.ctx.derived.attackBonus(true);
    const powerPenalty = -1;
    const powerBonus = k.twoHanded ? 3 : 2;
    const roll = this.ctx.dice.d20Roll();
    const total = roll + atkBonus + powerPenalty;
    const targetAc = k.targetAc ?? 10;
    const hit = total >= targetAc;
    const lines = [`💥 猛力攻击: d20+${atkBonus}${powerPenalty} = ${roll}+${atkBonus + powerPenalty} = ${total} vs AC ${targetAc}`];
    if (hit) {
      const weapon = this.ctx.equipment.getEquippedWeapon();
      const [dmgRolls, dmgDesc] = this.ctx.dice.rollWeaponDamageStr(weapon);
      let strMod = this.strMod();
      if (k.twoHanded) strMod = Math.floor(strMod * 1.5);
      const totalDmg = dmgRolls.reduce((a: number, b: number) => a + b, 0) + strMod + powerBonus;
      lines.push(`  ✓ 命中！伤害: ${dmgDesc}+${strMod}(力量)+${powerBonus}(猛力) = ${totalDmg}`);
    } else lines.push("  ✗ 未命中");
    return lines.join("\n");
  }

  private macroWhirlwind(k: any = {}): string {
    if (!this.ctx.techniques.hasTechnique("旋风切割")) return "未学会「旋风切割」技术";
    const atkBonus = this.ctx.derived.attackBonus(true);
    const penalty = this.TECHNIQUES["旋风切割"][3];
    const targetAc = k.targetAc ?? 10;
    const numTargets = k.numTargets ?? 2;
    const lines = [`🌀 旋风切割 (惩罚${penalty}):`];
    for (let i = 0; i < numTargets; i++) {
      const roll = this.ctx.dice.d20Roll();
      const total = roll + atkBonus + penalty;
      const hit = total >= targetAc;
      if (hit) {
        const weapon = this.ctx.equipment.getEquippedWeapon();
        const [dmgRolls] = this.ctx.dice.rollWeaponDamageStr(weapon);
        const totalDmg = dmgRolls.reduce((a: number, b: number) => a + b, 0) + this.strMod();
        lines.push(`  目标${i + 1}: d20=${roll} 总=${total} ✓ 命中 伤害=${totalDmg}`);
      } else lines.push(`  目标${i + 1}: d20=${roll} 总=${total} ✗ 未命中`);
    }
    return lines.join("\n");
  }

  // ---------- 法术宏（消耗法术位 + 上环） ----------
  private macroFireball(k: any = {}): string {
    if (!this.ctx.techniques.hasTechnique("火球术")) return "未学会「火球术」技术";
    const ring = Math.max(k.upcast || SPELL_RINGS["火球术"], SPELL_RINGS["火球术"]);
    const [ok, msg] = this.spend(ring);
    if (!ok) return `施法失败：${msg}`;
    const castBonus = (this.ctx as any).skills.effectiveSkillRank("施法攻击");
    const roll = this.ctx.dice.d20Roll();
    const total = roll + castBonus;
    const dc = k.dc ?? 15;
    const penalty = this.TECHNIQUES["火球术"][3];
    const up = ring - SPELL_RINGS["火球术"];
    const lines = [`🔥 火球术(${ring}环): 施法检定 d20+${castBonus} = ${roll}+${castBonus} = ${total} vs DC ${dc}`];
    if (total + penalty >= dc) {
      const dmg = this.dmgRolls(8 + up, 6, "火");
      lines.push(`  伤害: ${8 + up}d6 = ${dmg} = ${dmg.reduce((a: number, b: number) => a + b, 0)} 火焰`);
      const numTargets = k.numTargets ?? 1;
      if (numTargets > 1) lines.push(`  命中 ${numTargets} 个目标！每个目标受到 ${dmg.reduce((a: number, b: number) => a + b, 0)} 火焰伤害`);
    } else lines.push("  ✗ 施法失败");
    return lines.join("\n");
  }

  private macroMagicMissile(k: any = {}): string {
    if (!this.ctx.techniques.hasTechnique("魔法飞弹")) return "未学会「魔法飞弹」技术";
    const ring = Math.max(k.upcast || 1, SPELL_RINGS["魔法飞弹"]);
    const [ok, msg] = this.spend(ring);
    if (!ok) return `施法失败：${msg}`;
    const missiles = 3 + (ring - 1);
    const lines = [`✨ 魔法飞弹(${ring}环，${missiles}发，自动命中):`];
    let total = 0;
    for (let i = 0; i < missiles; i++) {
      const d = rand(4) + 1;
      total += d;
      lines.push(`  第${i + 1}发: 1d4+1 = ${d}`);
    }
    const numTargets = k.numTargets ?? 1;
    if (numTargets > 1) lines.push(`  分散打击 ${Math.min(numTargets, missiles)} 个目标，共造成 ${total} 力场伤害`);
    else lines.push(`  单目标共造成 ${total} 力场伤害`);
    return lines.join("\n");
  }

  private macroHealingWord(k: any = {}): string {
    if (!this.ctx.techniques.hasTechnique("治疗言灵")) return "未学会「治疗言灵」技术";
    const ring = Math.max(k.upcast || 1, SPELL_RINGS["治疗言灵"]);
    const [ok, msg] = this.spend(ring);
    if (!ok) return `施法失败：${msg}`;
    const castMod = Math.floor((this.ctx.state.attributes["智力"] - 10) / 2);
    const dice = 1 + (ring - 1);
    const heal = Array.from({ length: dice }, () => rand(4)).reduce((a: number, b: number) => a + b, 0) + Math.max(castMod, 1);
    this.ctx.rest.heal(heal);
    return `💚 治疗言灵(${ring}环): ${dice}d4+${Math.max(castMod, 1)} = ${heal} 生命恢复`;
  }

  private macroFireBolt(k: any = {}): string {
    if (!this.ctx.techniques.hasTechnique("火焰箭")) return "未学会「火焰箭」戏法";
    const castBonus = (this.ctx as any).skills.effectiveSkillRank("施法攻击");
    const roll = this.ctx.dice.d20Roll();
    const total = roll + castBonus;
    const targetAc = k.targetAc ?? 10;
    const lines = [`🔥 火焰箭(戏法): 施法检定 d20+${castBonus} = ${total} vs AC ${targetAc}`];
    if (total >= targetAc) {
      const dmg = this.dmgRolls(1, 10, "火");
      lines.push(`  ✓ 命中！伤害: 1d10 = ${dmg[0]} 火焰`);
    } else lines.push("  ✗ 未命中");
    return lines.join("\n");
  }

  private macroRayOfFrost(k: any = {}): string {
    if (!this.ctx.techniques.hasTechnique("霜冻射线")) return "未学会「霜冻射线」戏法";
    const castBonus = (this.ctx as any).skills.effectiveSkillRank("施法攻击");
    const roll = this.ctx.dice.d20Roll();
    const total = roll + castBonus;
    const targetAc = k.targetAc ?? 10;
    const lines = [`❄ 霜冻射线(戏法): 施法检定 d20+${castBonus} = ${total} vs AC ${targetAc}`];
    if (total >= targetAc) {
      const dmg = this.dmgRolls(1, 8, "寒");
      lines.push(`  ✓ 命中！伤害: 1d8 = ${dmg[0]} 寒冷`);
    } else lines.push("  ✗ 未命中");
    return lines.join("\n");
  }

  private macroScorchingRay(k: any = {}): string {
    if (!this.ctx.techniques.hasTechnique("灼热射线")) return "未学会「灼热射线」技术";
    const ring = Math.max(k.upcast || 2, SPELL_RINGS["灼热射线"]);
    const [ok, msg] = this.spend(ring);
    if (!ok) return `施法失败：${msg}`;
    const rays = 3 + (ring - 2);
    const castBonus = (this.ctx as any).skills.effectiveSkillRank("施法攻击");
    const targetAc = k.targetAc ?? 10;
    const lines = [`☀ 灼热射线(${ring}环，${rays}道):`];
    let total = 0;
    for (let i = 0; i < rays; i++) {
      const roll = this.ctx.dice.d20Roll();
      if (roll + castBonus >= targetAc) {
        const dmg = this.dmgRolls(2, 6, "火");
        total += dmg.reduce((a: number, b: number) => a + b, 0);
        lines.push(`  第${i + 1}道: d20+${castBonus}=${roll + castBonus} ✓ 命中 2d6=${dmg} 火焰`);
      } else lines.push(`  第${i + 1}道: d20+${castBonus}=${roll + castBonus} ✗ 未命中`);
    }
    lines.push(`  共造成 ${total} 火焰伤害`);
    return lines.join("\n");
  }

  private macroLightningBolt(k: any = {}): string {
    if (!this.ctx.techniques.hasTechnique("闪电束")) return "未学会「闪电束」技术";
    const ring = Math.max(k.upcast || 3, SPELL_RINGS["闪电束"]);
    const [ok, msg] = this.spend(ring);
    if (!ok) return `施法失败：${msg}`;
    const castBonus = (this.ctx as any).skills.effectiveSkillRank("施法攻击");
    const roll = this.ctx.dice.d20Roll();
    const total = roll + castBonus;
    const dc = k.dc ?? 15;
    const penalty = this.TECHNIQUES["闪电束"][3];
    const up = ring - 3;
    const lines = [`⚡ 闪电束(${ring}环): 施法检定 d20+${castBonus} = ${total} vs DC ${dc}`];
    if (total + penalty >= dc) {
      const dmg = this.dmgRolls(8 + up, 6, "电");
      lines.push(`  伤害: ${8 + up}d6 = ${dmg} = ${dmg.reduce((a: number, b: number) => a + b, 0)} 闪电`);
    } else lines.push("  ✗ 施法失败");
    return lines.join("\n");
  }

  private macroConeOfCold(k: any = {}): string {
    if (!this.ctx.techniques.hasTechnique("寒冰锥")) return "未学会「寒冰锥」技术";
    const ring = Math.max(k.upcast || 5, SPELL_RINGS["寒冰锥"]);
    const [ok, msg] = this.spend(ring);
    if (!ok) return `施法失败：${msg}`;
    const castBonus = (this.ctx as any).skills.effectiveSkillRank("施法攻击");
    const roll = this.ctx.dice.d20Roll();
    const total = roll + castBonus;
    const dc = k.dc ?? 17;
    const penalty = this.TECHNIQUES["寒冰锥"][3];
    const up = ring - 5;
    const lines = [`❄ 寒冰锥(${ring}环): 施法检定 d20+${castBonus} = ${total} vs DC ${dc}`];
    if (total + penalty >= dc) {
      const dmg = this.dmgRolls(8 + up, 8, "寒");
      lines.push(`  伤害: ${8 + up}d8 = ${dmg} = ${dmg.reduce((a: number, b: number) => a + b, 0)} 寒冷`);
    } else lines.push("  ✗ 施法失败");
    return lines.join("\n");
  }

  private macroMeteorSwarm(k: any = {}): string {
    if (!this.ctx.techniques.hasTechnique("陨石雨")) return "未学会「陨石雨」技术";
    const [ok, msg] = this.spend(9);
    if (!ok) return `施法失败：${msg}`;
    const castBonus = (this.ctx as any).skills.effectiveSkillRank("施法攻击");
    const roll = this.ctx.dice.d20Roll();
    const total = roll + castBonus;
    const dc = k.dc ?? 20;
    const penalty = this.TECHNIQUES["陨石雨"][3];
    const lines = [`☄ 陨石雨(9环): 施法检定 d20+${castBonus} = ${total} vs DC ${dc}`];
    if (total + penalty >= dc) {
      const dmg = this.dmgRolls(40, 6, "火");
      lines.push(`  伤害: 40d6 = ${dmg.reduce((a: number, b: number) => a + b, 0)} 火焰+钝击（范围毁灭）`);
    } else lines.push("  ✗ 施法失败");
    return lines.join("\n");
  }

  private macroDragonBreath(): string {
    if (this.ctx.state.race !== "龙裔") return "非龙裔种族，无法使用龙息";
    const st = this.ctx.state;
    if (st.breathUsed) return "龙息已使用（短休后充能）";
    const elem = this.ctx.race.elemental();
    const dmg = this.dmgRolls(2, 6, elem);
    st.breathUsed = true;
    return `🐉 龙息(${elem}): 2d6 = ${dmg} = ${dmg.reduce((a: number, b: number) => a + b, 0)} ${elem}伤害（范围喷吐）`;
  }

  // ====================================================================
  //  GURPS 风格战技（Maneuver / Technique）
  // ====================================================================
  private macroDeceptiveAttack(k: any = {}): string {
    if (!this.ctx.techniques.hasTechnique("欺诈攻击")) return "未学会「欺诈攻击」技术";
    const atkBonus = this.ctx.derived.attackBonus(true);
    const penalty = -2;
    if (atkBonus + penalty < 10) return "技能有效等级不足（欺诈攻击不可使技能低于10）";
    const foeDefPen = Math.abs(penalty) / 2;
    const roll = this.ctx.dice.d20Roll();
    const total = roll + atkBonus + penalty;
    const targetAc = k.targetAc ?? 10;
    const effectiveAc = Math.max(targetAc - foeDefPen, 5);
    const hit = total >= effectiveAc;
    const lines = [`🎭 欺诈攻击: d20+${atkBonus}${penalty} = ${total} (敌方AC${targetAc}-${foeDefPen}=${effectiveAc})`];
    if (hit) lines.push(this.weaponHit(this.ctx.equipment.getEquippedWeapon(), this.strMod()));
    else lines.push("  ✗ 未命中");
    return lines.join("\n");
  }

  private macroRapidStrike(k: any = {}): string {
    if (!this.ctx.techniques.hasTechnique("连环打击")) return "未学会「连环打击」技术";
    const atkBonus = this.ctx.derived.attackBonus(true);
    const penalty = this.TECHNIQUES["连环打击"][3];
    const targetAc = k.targetAc ?? 10;
    const lines = [`⚡ 连环打击 (各${penalty}):`];
    for (let i = 0; i < 2; i++) {
      const roll = this.ctx.dice.d20Roll();
      const total = roll + atkBonus + penalty;
      const hit = total >= targetAc;
      if (hit) {
        const weapon = this.ctx.equipment.getEquippedWeapon();
        const [dmgRolls] = this.ctx.dice.rollWeaponDamageStr(weapon);
        const totalDmg = dmgRolls.reduce((a: number, b: number) => a + b, 0) + this.strMod();
        lines.push(`  第${i + 1}击: d20=${roll} 总=${total} ✓ 命中 伤害=${totalDmg}`);
      } else lines.push(`  第${i + 1}击: d20=${roll} 总=${total} ✗ 未命中`);
    }
    return lines.join("\n");
  }

  private macroAlloutStrong(k: any = {}): string {
    if (!this.ctx.techniques.hasTechnique("全力强击")) return "未学会「全力强击」技术";
    const atkBonus = this.ctx.derived.attackBonus(true);
    const roll = this.ctx.dice.d20Roll();
    const total = roll + atkBonus;
    const targetAc = k.targetAc ?? 10;
    const lines = [`💪 全力强击: d20+${atkBonus} = ${total} vs AC ${targetAc} (本回合无法防御！)`];
    if (total >= targetAc) {
      const weapon = this.ctx.equipment.getEquippedWeapon();
      const [dmgRolls, dmgDesc] = this.ctx.dice.rollWeaponDamageStr(weapon);
      let strMod = this.strMod();
      if (k.twoHanded) strMod = Math.floor(strMod * 1.5);
      const totalDmg = dmgRolls.reduce((a: number, b: number) => a + b, 0) + strMod + 2;
      lines.push(`  ✓ 命中！伤害: ${dmgDesc}+${strMod}(力量)+2(全力) = ${totalDmg}`);
    } else lines.push("  ✗ 未命中");
    return lines.join("\n");
  }

  private macroAlloutDetermined(k: any = {}): string {
    if (!this.ctx.techniques.hasTechnique("精准突击")) return "未学会「精准突击」技术";
    const atkBonus = this.ctx.derived.attackBonus(true);
    const roll = this.ctx.dice.d20Roll();
    const total = roll + atkBonus + 4;
    const targetAc = k.targetAc ?? 10;
    const lines = [`🎯 精准突击: d20+${atkBonus}+4 = ${total} vs AC ${targetAc} (本回合无法防御！)`];
    if (total >= targetAc) lines.push(this.weaponHit(this.ctx.equipment.getEquippedWeapon(), this.strMod()));
    else lines.push("  ✗ 未命中");
    return lines.join("\n");
  }
}
