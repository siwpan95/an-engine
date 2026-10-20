"""data/sample_thief.py - 示例角色构建脚本

复现 盗贼.txt（同目录）的角色，演示用 allin_engine.trpg 构建角色的完整流程。
运行：python -m allin_engine.trpg.samples.sample_thief
"""

# 本文件自 siwpan/d20 并入（2026-10-20）：d20 仓确诊为「薄 shim + 界面壳」，规则内核早在本仓 allin_engine.trpg，界面壳迁入此处后原仓删除。

from allin_engine.trpg import Character


def build_thief() -> Character:
    """构建一个盗贼角色。"""
    c = Character(150)
    c.set_attribute("力量", 11)
    c.set_attribute("体质", 13)
    c.add_advantage("昏暗视觉", 2)
    c.add_disadvantage("荣誉准则", 10)
    c.add_talent("轻巧战法", 1)
    for sk, lvl in [("反射豁免", 10), ("强韧豁免", 10), ("意志豁免", 10),
                    ("活力", 14), ("潜行", 10), ("躲藏", 10),
                    ("近战攻击", 10)]:
        c.purchase_skill(sk, lvl)
    c.purchase_technique("偷袭要害打击")
    c.equip_item("匕首")
    c.equip_item("全身板甲")
    c.equip_item("铁盾")
    return c


if __name__ == "__main__":
    thief = build_thief()
    print(thief.show_sheet())
    print("\n=== 战斗演示 ===")
    print(thief.combat_macro("sneak_attack", target_ac=15, flat_footed=True))
    print("---")
    print(thief.gurps_check("潜行"))
