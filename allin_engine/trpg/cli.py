"""cli.py - D&D-GURPS 变体角色构建器命令行界面

基于 allin_engine.trpg，提供交互式角色构建、掷骰测试与战斗宏演示。
运行：python -m allin_engine.trpg.cli   （或控制台脚本 allin-trpg）
"""

# 本文件自 siwpan/d20 并入（2026-10-20）：d20 仓确诊为「薄 shim + 界面壳」，规则内核早在本仓 allin_engine.trpg，界面壳迁入此处后原仓删除。

from allin_engine.trpg import Character


def _set_attributes(char: Character):
    for attr in ["力量", "敏捷", "体质", "智力", "感知", "魅力"]:
        while True:
            val = input(f"  {attr} (当前{char.attributes[attr]}, 输入新值或回车跳过): ").strip()
            if val == "":
                break
            try:
                ok, msg = char.set_attribute(attr, int(val))
                print(f"  {msg}")
                if ok:
                    break
            except ValueError:
                print("  请输入数字")


def _perks(char: Character):
    print("  优点库:")
    for i, (n, c) in enumerate(char.ADVANTAGES_LIBRARY.items(), 1):
        print(f"    {i}. {n} ({c}CP)")
    print("  缺点库:")
    base = len(char.ADVANTAGES_LIBRARY)
    for i, (n, r) in enumerate(char.DISADVANTAGES_LIBRARY.items(), 1):
        print(f"    {base+i}. {n} (+{r}CP)")
    choice = input("  输入名称添加, 0返回: ").strip()
    if choice == "0" or not choice:
        return
    if choice in char.ADVANTAGES_LIBRARY:
        print("  " + " ".join(char.add_advantage_by_name(choice)))
    elif choice in char.DISADVANTAGES_LIBRARY:
        print("  " + " ".join(char.add_disadvantage_by_name(choice)))
    else:
        print("  未知项")


def _talents(char: Character):
    print("  天赋列表 (每级5CP):")
    for name in char.TALENT_BONUS_GROUPS:
        skills = ", ".join(char.TALENT_BONUS_GROUPS[name])
        print(f"    {name} -> {skills}")
    tname = input("  天赋名: ").strip()
    if not tname:
        return
    level = input("  等级(1-3, 默认1): ").strip()
    level = int(level) if level else 1
    print("  " + " ".join(char.add_talent(tname, level)))


def _skills(char: Character):
    print("  技能列表:")
    items = list(char.SKILL_LIBRARY.items())
    for i, (sk, (attr, diff, _)) in enumerate(items, 1):
        cur = char.skills.get(sk, 0)
        print(f"    {i}. {sk} ({attr}/{diff}) 当前:{cur}")
    try:
        idx = int(input("  选择技能编号: ")) - 1
        sk_name = items[idx][0]
        target = int(input(f"  目标绝对等级: "))
        print("  " + " ".join(char.purchase_skill(sk_name, target)))
    except (ValueError, IndexError):
        print("  无效输入")


def _techniques(char: Character):
    print("  技术列表:")
    items = list(char.TECHNIQUES.items())
    for i, (tech, (req, rank, attr_req, _pen, cost, desc)) in enumerate(items, 1):
        owned = "✓" if tech in char.techniques else " "
        print(f"    {i}. [{owned}] {tech} (需{req}{rank} {attr_req or ''}, CP:{cost}) - {desc}")
    try:
        idx = int(input("  选择技术编号: ")) - 1
        tech_name = items[idx][0]
        print("  " + " ".join(char.purchase_technique(tech_name)))
    except (ValueError, IndexError):
        print("  无效输入")


def _equipment(char: Character):
    print("  装备库:")
    items = list(char.EQUIPMENT_LIBRARY.items())
    for i, (name, (etype, sub, armor, _md, _w, desc, cp)) in enumerate(items, 1):
        owned = "✓" if name in char.equipment else " "
        print(f"    {i}. [{owned}] {name} ({etype}/{sub}, AC+{armor}, {cp}CP) - {desc}")
    sub = input("  [e]装备 [u]卸下 [0]返回: ").strip()
    if sub == "e":
        try:
            idx = int(input("  装备编号: ")) - 1
            print("  " + " ".join(char.equip_item(items[idx][0])))
        except (ValueError, IndexError):
            print("  无效输入")
    elif sub == "u":
        if not char.equipment:
            print("  未装备任何物品")
            return
        for i, name in enumerate(char.equipment, 1):
            print(f"    {i}. {name}")
        try:
            idx = int(input("  卸下编号: ")) - 1
            print("  " + " ".join(char.unequip_item(char.equipment[idx])))
        except (ValueError, IndexError):
            print("  无效输入")


def _roll_test(char: Character):
    print("  1. D20检定  2. D100技能成功率  3. GURPS 3d6检定  4. D6伤害")
    t = input("  选: ").strip()
    if t == "1":
        sk = input("  技能名: ").strip()
        dc = int(input("  DC: "))
        print("  " + char.d20_check(sk, dc))
    elif t == "2":
        sk = input("  技能名: ").strip()
        print("  " + char.d100_check(sk))
    elif t == "3":
        sk = input("  技能名: ").strip()
        print("  " + char.gurps_check(sk))
    elif t == "4":
        n = int(input("  骰数: "))
        m = int(input("  加值: "))
        print("  " + char.roll_d6(n, m))


def _combat_demo(char: Character):
    macros = ["melee_attack", "sneak_attack", "power_attack", "whirlwind",
              "fireball", "magic_missile", "healing_word",
              "deceptive_attack", "rapid_strike", "allout_strong", "allout_determined"]
    for i, m in enumerate(macros, 1):
        print(f"    {i}. {m}")
    try:
        idx = int(input("  选择宏编号: ")) - 1
        m = macros[idx]
        print(char.combat_macro(m, target_ac=12, num_targets=2, flat_footed=True))
    except (ValueError, IndexError):
        print("  无效输入")


def main():
    char = Character()
    print("=" * 50)
    print(" D&D-GURPS 变体角色构建器 v3.0")
    print(" 融合 D&D 三宝书 + GURPS Basic Set 规则")
    print("=" * 50)
    while True:
        print(f"\n当前 CP: {char.cp} | HP: {char.hp()} | AC: {char.ac}")
        print("1.属性  2.优缺点  3.天赋  4.技能  5.技术  6.装备  "
              "7.角色卡  8.掷骰  9.战斗宏  0.完成退出")
        cmd = input("选择: ").strip()
        if cmd == "1":
            _set_attributes(char)
        elif cmd == "2":
            _perks(char)
        elif cmd == "3":
            _talents(char)
        elif cmd == "4":
            _skills(char)
        elif cmd == "5":
            _techniques(char)
        elif cmd == "6":
            _equipment(char)
        elif cmd == "7":
            print(char.show_sheet())
        elif cmd == "8":
            _roll_test(char)
        elif cmd == "9":
            _combat_demo(char)
        elif cmd == "0":
            missing = char.check_foundations()
            if missing:
                print(f"⚠ 警告: 缺少根基科 {', '.join(missing)}，请至少投入1级")
            else:
                print("✓ 角色创建完成！最终角色卡：")
                print(char.show_sheet())
            break
        else:
            print("无效选择")


if __name__ == "__main__":
    main()
