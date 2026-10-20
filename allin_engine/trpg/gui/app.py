"""gui.app - D&D-GURPS 变体角色构建器 tkinter 图形界面

基于 allin_engine.trpg。相比原 mvp_gui，新增：更多优缺点按钮、GURPS 战技宏、
GURPS 3d6 检定、灵巧武器高亮等增强内容。
运行：python -m allin_engine.trpg.gui
"""

# 本文件自 siwpan/d20 并入（2026-10-20）：d20 仓确诊为「薄 shim + 界面壳」，规则内核早在本仓 allin_engine.trpg，界面壳迁入此处后原仓删除。

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from allin_engine.trpg import Character


class CharacterBuilderApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("D&D-GURPS 变体角色构建器 v3.0")
        self.root.geometry("1040x760")
        self.root.minsize(860, 640)

        self.char = Character()
        self._build_ui()
        self._refresh_all()

    # ================================================================
    #  UI 构建
    # ================================================================
    def _build_ui(self):
        # 顶部状态栏
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(fill=tk.X, padx=6, pady=4)
        self.cp_var = tk.StringVar(value="CP: 150")
        ttk.Label(self.status_frame, textvariable=self.cp_var,
                  font=("Microsoft YaHei", 14, "bold")).pack(side=tk.LEFT)
        ttk.Label(self.status_frame,
                  text="融合 D&D 三宝书 + GURPS Basic Set",
                  foreground="#666").pack(side=tk.LEFT, padx=12)

        # Notebook
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        self._build_attr_tab()
        self._build_skill_tab()
        self._build_talent_tab()
        self._build_equip_tab()
        self._build_combat_tab()
        self._build_sheet_tab()

    # ---------- 属性页 ----------
    def _build_attr_tab(self):
        frame = ttk.Frame(self.nb)
        self.nb.add(frame, text="属性")

        self.attr_vars: dict[str, tk.IntVar] = {}
        self.attr_labels: dict[str, ttk.Label] = {}
        attrs = ["力量", "敏捷", "体质", "智力", "感知", "魅力"]

        for attr in attrs:
            row = ttk.Frame(frame)
            row.pack(fill=tk.X, padx=12, pady=4)

            ttk.Label(row, text=attr, width=8,
                      font=("Microsoft YaHei", 11)).pack(side=tk.LEFT)

            var = tk.IntVar(value=10)
            self.attr_vars[attr] = var

            spin = ttk.Spinbox(row, from_=10, to=25, textvariable=var,
                               width=5, command=lambda a=attr: self._on_attr_change(a))
            spin.pack(side=tk.LEFT, padx=4)
            spin.bind("<Return>", lambda e, a=attr: self._on_attr_change(a))

            mod_label = ttk.Label(row, text="调整值: +0", width=12)
            mod_label.pack(side=tk.LEFT, padx=4)
            self.attr_labels[attr] = mod_label

            ttk.Label(row, text="花费: 0 CP", width=14).pack(side=tk.LEFT, padx=4)

    def _on_attr_change(self, attr: str):
        new_val = self.attr_vars[attr].get()
        ok, msg = self.char.set_attribute(attr, new_val)
        if not ok:
            messagebox.showwarning("设置失败", msg)
            self.attr_vars[attr].set(self.char.attributes[attr])
        self._refresh_all()

    # ---------- 技能页 ----------
    def _build_skill_tab(self):
        frame = ttk.Frame(self.nb)
        self.nb.add(frame, text="技能")

        left = ttk.Frame(frame)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)

        cols = ("skill", "attr", "diff", "rank", "default", "total", "found")
        self.skill_tree = ttk.Treeview(left, columns=cols, show="headings", height=20)
        self.skill_tree.heading("skill", text="技能")
        self.skill_tree.heading("attr", text="属性")
        self.skill_tree.heading("diff", text="难度")
        self.skill_tree.heading("rank", text="等级")
        self.skill_tree.heading("default", text="默认值")
        self.skill_tree.heading("total", text="有效值")
        self.skill_tree.heading("found", text="根基")
        self.skill_tree.column("skill", width=100)
        self.skill_tree.column("attr", width=50)
        self.skill_tree.column("diff", width=50)
        self.skill_tree.column("rank", width=50)
        self.skill_tree.column("default", width=60)
        self.skill_tree.column("total", width=60)
        self.skill_tree.column("found", width=50)
        self.skill_tree.pack(fill=tk.BOTH, expand=True)

        right = ttk.LabelFrame(frame, text="购买技能")
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=4, pady=4)

        ttk.Label(right, text="目标等级:").pack(padx=8, pady=(8, 2))
        self.skill_target_var = tk.IntVar(value=1)
        ttk.Spinbox(right, from_=1, to=25, textvariable=self.skill_target_var,
                     width=8).pack(padx=8)
        ttk.Button(right, text="购买", command=self._purchase_skill).pack(padx=8, pady=6)
        ttk.Button(right, text="刷新", command=self._refresh_skills).pack(padx=8, pady=2)

    def _purchase_skill(self):
        sel = self.skill_tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一个技能")
            return
        skill_name = self.skill_tree.item(sel[0])["values"][0]
        target = self.skill_target_var.get()
        ok, msg = self.char.purchase_skill(str(skill_name), target)
        if not ok:
            messagebox.showwarning("购买失败", msg)
        self._refresh_all()

    def _refresh_skills(self):
        self.skill_tree.delete(*self.skill_tree.get_children())
        for skill, (attr, diff, is_found) in self.char.SKILL_LIBRARY.items():
            rank = self.char.skills.get(skill, 0)
            default = self.char.effective_skill_rank(skill) if rank == 0 else "-"
            total = self.char.effective_skill_rank(skill)
            found = "★" if is_found else ""
            self.skill_tree.insert("", tk.END,
                values=(skill, attr, diff, rank, default, total, found))

    # ---------- 天赋/优缺点页 ----------
    def _build_talent_tab(self):
        frame = ttk.Frame(self.nb)
        self.nb.add(frame, text="天赋/优缺点")

        # 优点
        adv_frame = ttk.LabelFrame(frame, text="优点")
        adv_frame.pack(fill=tk.X, padx=6, pady=4)
        advs = list(self.char.ADVANTAGES_LIBRARY.items())
        # 分行排列
        for i in range(0, len(advs), 5):
            row = ttk.Frame(adv_frame)
            row.pack(fill=tk.X, padx=4, pady=2)
            for name, cost in advs[i:i+5]:
                ttk.Button(row, text=f"{name}({cost})",
                           command=lambda n=name: self._add_advantage(n)
                           ).pack(side=tk.LEFT, padx=2)

        # 缺点
        dis_frame = ttk.LabelFrame(frame, text="缺点")
        dis_frame.pack(fill=tk.X, padx=6, pady=4)
        diss = list(self.char.DISADVANTAGES_LIBRARY.items())
        for i in range(0, len(diss), 5):
            row = ttk.Frame(dis_frame)
            row.pack(fill=tk.X, padx=4, pady=2)
            for name, cp_ret in diss[i:i+5]:
                ttk.Button(row, text=f"{name}(+{cp_ret})",
                           command=lambda n=name: self._add_disadvantage(n)
                           ).pack(side=tk.LEFT, padx=2)

        # 天赋
        tal_frame = ttk.LabelFrame(frame, text="天赋 (每级5CP)")
        tal_frame.pack(fill=tk.X, padx=6, pady=4)

        row = ttk.Frame(tal_frame)
        row.pack(fill=tk.X, padx=4, pady=4)
        ttk.Label(row, text="天赋名:").pack(side=tk.LEFT)
        self.talent_name_var = tk.StringVar()
        ttk.Combobox(row, textvariable=self.talent_name_var, width=12,
                     values=list(self.char.TALENT_BONUS_GROUPS.keys())
                     ).pack(side=tk.LEFT, padx=4)
        ttk.Label(row, text="等级:").pack(side=tk.LEFT)
        self.talent_level_var = tk.IntVar(value=1)
        ttk.Spinbox(row, from_=1, to=3, textvariable=self.talent_level_var,
                     width=4).pack(side=tk.LEFT, padx=4)
        ttk.Button(row, text="购买天赋", command=self._add_talent).pack(side=tk.LEFT, padx=4)

        # 技术
        tech_frame = ttk.LabelFrame(frame, text="技术")
        tech_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        self.tech_list = tk.Listbox(tech_frame, height=8)
        self.tech_list.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        ttk.Button(tech_frame, text="购买选中技术",
                   command=self._purchase_tech).pack(padx=4, pady=4)

    def _add_advantage(self, name):
        ok, msg = self.char.add_advantage_by_name(name)
        if not ok:
            messagebox.showwarning("失败", msg)
        self._refresh_all()

    def _add_disadvantage(self, name):
        ok, msg = self.char.add_disadvantage_by_name(name)
        if not ok:
            messagebox.showwarning("失败", msg)
        self._refresh_all()

    def _add_talent(self):
        name = self.talent_name_var.get()
        level = self.talent_level_var.get()
        if not name:
            messagebox.showinfo("提示", "请选择天赋")
            return
        ok, msg = self.char.add_talent(name, level)
        if not ok:
            messagebox.showwarning("失败", msg)
        self._refresh_all()

    def _purchase_tech(self):
        sel = self.tech_list.curselection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一个技术")
            return
        tech_name = self.tech_list.get(sel[0]).split("|")[0].strip()
        ok, msg = self.char.purchase_technique(tech_name)
        if not ok:
            messagebox.showwarning("购买失败", msg)
        self._refresh_all()

    def _refresh_techs(self):
        self.tech_list.delete(0, tk.END)
        for tech, (req, rank, attr_req, pen, cost, desc) in self.char.TECHNIQUES.items():
            owned = "✓" if tech in self.char.techniques else " "
            self.tech_list.insert(tk.END,
                f"{tech} | 需{req}{rank} CP:{cost} | {desc} {owned}")

    # ---------- 装备页 ----------
    def _build_equip_tab(self):
        frame = ttk.Frame(self.nb)
        self.nb.add(frame, text="装备")

        left = ttk.LabelFrame(frame, text="装备库")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)

        cols = ("name", "type", "armor", "max_dex", "weight", "cp")
        self.equip_tree = ttk.Treeview(left, columns=cols, show="headings", height=16)
        self.equip_tree.heading("name", text="名称")
        self.equip_tree.heading("type", text="类型")
        self.equip_tree.heading("armor", text="AC+")
        self.equip_tree.heading("max_dex", text="敏捷上限")
        self.equip_tree.heading("weight", text="重量")
        self.equip_tree.heading("cp", text="CP")
        self.equip_tree.column("name", width=80)
        self.equip_tree.column("type", width=80)
        self.equip_tree.column("armor", width=40)
        self.equip_tree.column("max_dex", width=60)
        self.equip_tree.column("weight", width=40)
        self.equip_tree.column("cp", width=40)
        self.equip_tree.pack(fill=tk.BOTH, expand=True)

        ttk.Button(left, text="装备选中", command=self._equip_item).pack(pady=4)

        right = ttk.LabelFrame(frame, text="已装备")
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.equipped_list = tk.Listbox(right, height=16)
        self.equipped_list.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        ttk.Button(right, text="卸下选中", command=self._unequip_item).pack(pady=4)

        self._fill_equipment_library()

    def _fill_equipment_library(self):
        self.equip_tree.delete(*self.equip_tree.get_children())
        for name, (etype, sub, armor_b, max_dex, weight, desc, cp) in self.char.EQUIPMENT_LIBRARY.items():
            self.equip_tree.insert("", tk.END,
                values=(name, f"{etype}-{sub}", armor_b, max_dex, weight, cp))

    def _equip_item(self):
        sel = self.equip_tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一件装备")
            return
        item_name = self.equip_tree.item(sel[0])["values"][0]
        ok, msg = self.char.equip_item(str(item_name))
        if not ok:
            messagebox.showwarning("装备失败", msg)
        self._refresh_all()

    def _unequip_item(self):
        sel = self.equipped_list.curselection()
        if not sel:
            messagebox.showinfo("提示", "请先选择已装备物品")
            return
        item_name = self.equipped_list.get(sel[0]).split(" - ")[0].strip()
        ok, msg = self.char.unequip_item(item_name)
        if not ok:
            messagebox.showwarning("卸下失败", msg)
        self._refresh_all()

    def _refresh_equipment(self):
        self.equipped_list.delete(0, tk.END)
        for item in self.char.equipment:
            info = self.char.EQUIPMENT_LIBRARY[item]
            self.equipped_list.insert(tk.END,
                f"{item} - AC+{info[2]} 敏捷上限{info[3]}")

    # ---------- 战斗页 ----------
    def _build_combat_tab(self):
        frame = ttk.Frame(self.nb)
        self.nb.add(frame, text="战斗")

        macro_frame = ttk.LabelFrame(frame, text="战斗宏")
        macro_frame.pack(fill=tk.X, padx=6, pady=4)

        macros = [
            ("⚔ 普通近战", "melee_attack"),
            ("🗡 偷袭打击", "sneak_attack"),
            ("💥 猛力攻击", "power_attack"),
            ("🌀 旋风切割", "whirlwind"),
            ("🔥 火球术", "fireball"),
            ("✨ 魔法飞弹", "magic_missile"),
            ("💚 治疗言灵", "healing_word"),
            ("🎭 欺诈攻击", "deceptive_attack"),
            ("⚡ 连环打击", "rapid_strike"),
            ("💪 全力强击", "allout_strong"),
            ("🎯 精准突击", "allout_determined"),
        ]
        for i in range(0, len(macros), 6):
            row = ttk.Frame(macro_frame)
            row.pack(fill=tk.X, padx=4, pady=2)
            for label, macro_id in macros[i:i+6]:
                ttk.Button(row, text=label, width=12,
                           command=lambda m=macro_id: self._run_macro(m)
                           ).pack(side=tk.LEFT, padx=2)

        param_frame = ttk.LabelFrame(frame, text="参数")
        param_frame.pack(fill=tk.X, padx=6, pady=4)

        r1 = ttk.Frame(param_frame)
        r1.pack(fill=tk.X, padx=4, pady=2)
        ttk.Label(r1, text="目标AC:").pack(side=tk.LEFT)
        self.target_ac_var = tk.IntVar(value=12)
        ttk.Spinbox(r1, from_=5, to=40, textvariable=self.target_ac_var,
                     width=5).pack(side=tk.LEFT, padx=4)

        ttk.Label(r1, text="目标数:").pack(side=tk.LEFT, padx=(12, 0))
        self.num_targets_var = tk.IntVar(value=1)
        ttk.Spinbox(r1, from_=1, to=8, textvariable=self.num_targets_var,
                     width=4).pack(side=tk.LEFT, padx=4)

        ttk.Label(r1, text="措手不及:").pack(side=tk.LEFT, padx=(12, 0))
        self.flat_footed_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(r1, variable=self.flat_footed_var).pack(side=tk.LEFT)

        ttk.Label(r1, text="双手:").pack(side=tk.LEFT, padx=(12, 0))
        self.two_handed_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(r1, variable=self.two_handed_var).pack(side=tk.LEFT)

        # 检定
        check_frame = ttk.LabelFrame(frame, text="掷骰检定")
        check_frame.pack(fill=tk.X, padx=6, pady=4)
        r2 = ttk.Frame(check_frame)
        r2.pack(fill=tk.X, padx=4, pady=2)
        ttk.Label(r2, text="技能:").pack(side=tk.LEFT)
        self.check_skill_var = tk.StringVar(value="近战攻击")
        ttk.Entry(r2, textvariable=self.check_skill_var, width=10).pack(side=tk.LEFT, padx=4)
        ttk.Label(r2, text="DC:").pack(side=tk.LEFT)
        self.check_dc_var = tk.IntVar(value=12)
        ttk.Spinbox(r2, from_=1, to=40, textvariable=self.check_dc_var, width=5).pack(side=tk.LEFT, padx=4)
        ttk.Button(r2, text="D20检定", command=lambda: self._run_check("d20")).pack(side=tk.LEFT, padx=4)
        ttk.Button(r2, text="D100", command=lambda: self._run_check("d100")).pack(side=tk.LEFT, padx=4)
        ttk.Button(r2, text="GURPS 3d6", command=lambda: self._run_check("gurps")).pack(side=tk.LEFT, padx=4)

        # 结果显示
        self.combat_log = scrolledtext.ScrolledText(frame, height=14, state=tk.DISABLED,
                                                     font=("Consolas", 10))
        self.combat_log.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

    def _run_macro(self, macro_id: str):
        kwargs = {}
        if macro_id in ("melee_attack", "sneak_attack", "power_attack",
                        "whirlwind", "deceptive_attack", "rapid_strike",
                        "allout_strong", "allout_determined"):
            kwargs["target_ac"] = self.target_ac_var.get()
        if macro_id == "sneak_attack":
            kwargs["flat_footed"] = self.flat_footed_var.get()
        if macro_id in ("power_attack", "allout_strong"):
            kwargs["two_handed"] = self.two_handed_var.get()
        if macro_id == "whirlwind":
            kwargs["num_targets"] = self.num_targets_var.get()
        if macro_id in ("fireball", "magic_missile"):
            kwargs["num_targets"] = self.num_targets_var.get()

        result = self.char.combat_macro(macro_id, **kwargs)
        self._log(result)

    def _run_check(self, kind: str):
        sk = self.check_skill_var.get()
        if kind == "d20":
            self._log(self.char.d20_check(sk, self.check_dc_var.get()))
        elif kind == "d100":
            self._log(self.char.d100_check(sk))
        elif kind == "gurps":
            self._log(self.char.gurps_check(sk))

    def _log(self, text: str):
        self.combat_log.config(state=tk.NORMAL)
        self.combat_log.insert(tk.END, text + "\n" + "─" * 40 + "\n")
        self.combat_log.see(tk.END)
        self.combat_log.config(state=tk.DISABLED)

    # ---------- 角色卡页 ----------
    def _build_sheet_tab(self):
        frame = ttk.Frame(self.nb)
        self.nb.add(frame, text="角色卡")

        self.sheet_text = scrolledtext.ScrolledText(frame, font=("Consolas", 11),
                                                     state=tk.DISABLED)
        self.sheet_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        ttk.Button(frame, text="刷新角色卡",
                   command=self._refresh_sheet).pack(pady=4)

    def _refresh_sheet(self):
        self.sheet_text.config(state=tk.NORMAL)
        self.sheet_text.delete("1.0", tk.END)
        self.sheet_text.insert(tk.END, self.char.show_sheet())
        self.sheet_text.config(state=tk.DISABLED)

    # ================================================================
    #  全局刷新
    # ================================================================
    def _refresh_all(self):
        self.cp_var.set(f"CP: {self.char.cp}  |  HP: {self.char.hp()}  |  AC: {self.char.ac}")

        for attr, var in self.attr_vars.items():
            var.set(self.char.attributes[attr])
            mod = (self.char.attributes[attr] - 10) // 2
            self.attr_labels[attr].config(text=f"调整值: {mod:+d}")

        self._refresh_skills()
        self._refresh_techs()
        self._refresh_equipment()
        self._refresh_sheet()


def main():
    root = tk.Tk()
    CharacterBuilderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
