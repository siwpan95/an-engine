/* 引擎运行时烟雾测试：验证 TS 移植后的核心行为（零依赖，Node CJS 运行 emit 产物）。*/
const assert = require("assert");
const d20 = require("./dist-smoke/index.js");

function ok(cond, msg) { assert.ok(cond, "❌ " + msg); console.log("✓ " + msg); }

console.log("=== D20 web 引擎烟雾测试 ===");
const char = new d20.Character();
ok(char.cp === 150, `初始 CP=150 (实际 ${char.cp})`);

// 属性
let [s] = char.setAttribute("力量", 14);
ok(s === true, "设置力量=14 成功");
ok(char.attrMod("力量") === 2, `力量调整值=+2 (实际 ${char.attrMod("力量")})`);
ok(char.cp === 100, `力量14 消耗 50CP (剩余 ${char.cp})`);

// 技能
[s] = char.purchaseSkill("活力", 2);
ok(s === true, "购买活力 Lv.2 成功");
ok(char.effectiveSkillRank("活力") === 2, `活力有效等级=2 (实际 ${char.effectiveSkillRank("活力")})`);
ok(char.hp() > 0, `HP>0 (实际 ${char.hp()})`);

// 近战攻击 5 -> 解锁偷袭技术
char.purchaseSkill("近战攻击", 5);
char.purchaseSkill("闪避防御", 3);
[s] = char.purchaseTechnique("偷袭要害打击");
ok(s === true, "学习技术 偷袭要害打击 成功");

// 装备
[s] = char.equipItem("皮甲");
ok(s === true, "装备皮甲成功");
[s] = char.equipItem("短剑");
ok(s === true, "装备短剑成功");
ok(Number.isFinite(char.ac), `AC 为有限数值 (实际 ${char.ac})`);

// 优点/天赋
char.addAdvantageByName("昏暗视觉");
[s] = char.addTalent("轻巧战法", 1);
ok(s === true, "获得天赋 轻巧战法 Lv.1 成功");
ok(char.getTalentBonus("近战攻击") === 1, `轻巧战法 对近战攻击+1 (实际 ${char.getTalentBonus("近战攻击")})`);

// 组合契约：9 个服务已挂载
const ids = ["attributes","equipment","perks","techniques","skills","dice","derived","combat","sheet"];
for (const id of ids) ok(char.ctx.has(id), `服务已挂载: ${id}`);

// 战斗宏
const out = char.combatMacro("sneak_attack", {});
ok(out.includes("偷袭攻击"), "偷袭攻击战斗宏可运行");

// 插件热卸载：卸载 derived 后，依赖它的能力应报错（演示 web-cordis 式插件影响）
d20.unmountService(char.ctx, "derived");
let threw = false;
try { char.hp(); } catch (e) { threw = true; }
ok(threw, "卸载 derived 服务后 char.hp() 报错（插件影响可观测）");
// 重新挂载以恢复
d20.mountService(char.ctx, d20.COMPOSITION.find((e) => e.id === "derived"));
ok(Number.isFinite(char.hp()), "重新挂载 derived 后 HP 恢复");

// 角色卡渲染
const sheet = char.showSheet();
ok(sheet.includes("角色卡"), "showSheet 渲染出角色卡");
ok(sheet.includes("HP:"), "角色卡含 HP 行");

console.log("\n=== 盗贼复刻比对（与 Python data/sample_thief.py 基准一致） ===");
function buildThief() {
  const c = new d20.Character();
  c.setAttribute("力量", 11);
  c.setAttribute("体质", 13);
  c.addAdvantage("昏暗视觉", 2);
  c.addDisadvantage("荣誉准则", 10);
  c.addTalent("轻巧战法", 1);
  for (const [sk, lvl] of [["反射豁免", 10], ["强韧豁免", 10], ["意志豁免", 10],
    ["活力", 14], ["潜行", 10], ["躲藏", 10], ["近战攻击", 10]]) {
    c.purchaseSkill(sk, lvl);
  }
  c.purchaseTechnique("偷袭要害打击");
  c.equipItem("匕首");
  c.equipItem("全身板甲");
  c.equipItem("铁盾");
  return c;
}
const thief = buildThief();
ok(thief.cp === 1, `剩余 CP=1 (实际 ${thief.cp})`);
ok(thief.hp() === 65, `HP=65 (实际 ${thief.hp()})`);
ok(thief.ac === 20, `AC=20 (实际 ${thief.ac})`);
ok(thief.attackBonus(true) === 11, `近战=+11 (实际 ${thief.attackBonus(true)})`);
ok(thief.attackBonus(false) === 8, `远程=+8 (实际 ${thief.attackBonus(false)})`);
ok(thief.saveBonus("fort") === 11, `强韧=+11 (实际 ${thief.saveBonus("fort")})`);
ok(thief.saveBonus("ref") === 10, `反射=+10 (实际 ${thief.saveBonus("ref")})`);
ok(thief.saveBonus("will") === 10, `意志=+10 (实际 ${thief.saveBonus("will")})`);
ok(thief.effectiveSkillRank("远程攻击") === 8, `远程攻击默认值=8 (实际 ${thief.effectiveSkillRank("远程攻击")})`);
ok(thief.attrMod("体质") === 1, `体质调整值=+1 (实际 ${thief.attrMod("体质")})`);
ok(thief.attrMod("力量") === 0, `力量调整值=+0 (实际 ${thief.attrMod("力量")})`);

console.log("\n=== 扩充子系统（与 Python tests/test_expansion.py 基准一致） ===");
// 14 服务挂载
const all14 = ["attributes","background","combat","derived","dice","equipment","feats",
  "perks","race","rest","sheet","skills","slots","techniques"];
for (const id of all14) ok(char.ctx.has(id) || thief.ctx.has(id), `服务已挂载: ${id}`);

// 法术位（决策 A）
const mage = new d20.Character();
let [s2, m2] = mage.buySlot(1);
ok(s2 === false && m2.includes("奥术施法"), "无奥术施法不能买 1 环位");
mage.purchaseSkill("奥术施法", 1);
for (let i = 0; i < 4; i++) [s2] = mage.buySlot(1);
[s2, m2] = mage.buySlot(1);
ok(s2 === false && m2.includes("上限"), "1 环上限 4");
ok(mage.cp === 150 - 1 - 4, `法术位 CP 计价 (剩余 ${mage.cp})`);

// 专长（决策 B）
const f = new d20.Character();
f.addFeat("警觉");
ok(f.ctx.rest.initiativeBonus() === 5, `警觉先攻+5 (实际 ${f.ctx.rest.initiativeBonus()})`);
const f2 = new d20.Character();
f2.purchaseSkill("活力", 2);
const hpBefore = f2.hp();
f2.addFeat("强壮");
ok(f2.hp() === hpBefore + 4, `强壮 HP+2×活力 (实际 ${f2.hp()})`);

// 种族（决策 C）
const r1 = new d20.Character();
r1.setRace("人类");
ok(r1.cp === 90 && r1.attributes["力量"] === 11, `人类 60CP 全属性11 (剩余 ${r1.cp})`);
const r2 = new d20.Character();
r2.setRace("精灵");
ok(r2.cp === 122 && r2.attributes["敏捷"] === 12 && r2.advantages.includes("黑暗视觉"),
  `精灵 28CP 敏捷12 黑暗视觉 (剩余 ${r2.cp})`);
const r3 = new d20.Character();
r3.setRace("提夫林");
r3.purchaseSkill("活力", 2);
const dmgOut = r3.takeDamage(10, "火");
ok(dmgOut.includes("5 点"), `提夫林火焰抗性减半 (${dmgOut})`);
const r4 = new d20.Character();
r4.setRace("半兽人");
r4.purchaseSkill("活力", 2);
r4.takeDamage(999);
ok(r4.ctx.rest.currentHp() === 1, `半兽人濒死不屈 HP=1 (实际 ${r4.ctx.rest.currentHp()})`);

// 背景（决策 D）
const b1 = new d20.Character();
b1.setBackground("士兵");
b1.purchaseSkill("运动", 4);
ok(b1.effectiveSkillRank("运动") === 6, `背景熟练+2 (实际 ${b1.effectiveSkillRank("运动")})`);

// 休整（决策 E）
const e1 = new d20.Character();
e1.purchaseSkill("活力", 2);
ok(e1.ctx.rest.currentHp() === e1.hp(), "current_hp 初始=满血");
e1.takeDamage(3);
ok(e1.ctx.rest.currentHp() === e1.hp() - 3, `受伤跟踪 (实际 ${e1.ctx.rest.currentHp()})`);
e1.longRest();
ok(e1.ctx.rest.currentHp() === e1.hp(), "长休回满");

// 法术宏消耗法术位
const c1 = new d20.Character();
c1.purchaseSkill("奥术施法", 5);
c1.purchaseTechnique("火球术");
c1.buySlot(3);
const fb = c1.combatMacro("fireball", { dc: 1 });
ok(fb.includes("火球术(3环)") && c1.ctx.slots.available(3) === 0, "火球术消耗 3 环法术位");
const fb2 = c1.combatMacro("fireball", { dc: 1 });
ok(fb2.includes("施法失败"), "无法术位时施法失败");

// 角色卡新行
const s1 = new d20.Character();
s1.setRace("精灵");
s1.setBackground("学者");
s1.addFeat("警觉");
const sheet2 = s1.showSheet();
ok(sheet2.includes("种族: 精灵") && sheet2.includes("背景: 学者（研究者）") && sheet2.includes("专长: 警觉"),
  "角色卡含种族/背景/专长行");

console.log("\n全部烟雾测试通过 ✅");
