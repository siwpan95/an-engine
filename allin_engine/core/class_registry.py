"""
类注册表：类名 → 属性 / 信号 / 方法 元数据 + 轻量反射
==========================================================

来源：Godot ``core/object/class_db.*``（思路档，MIT）。
借用范围：**思路**（自研实现其「类元数据注册 + 反射查询」概念，
未搬 Godot 源码、未照抄命名 / 结构）。

Godot 的 ``ClassDB`` 维护一张「类名 → 属性 / 信号 / 方法」的全局表，
供编辑器反射与脚本绑定。本模块自研一张等价的元数据表，只保留
「注册 / 查询」这一层能力，不触碰 Godot 的对象 / 资源序列化。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Type


@dataclass
class ClassMeta:
    """一个类的元数据。"""

    name: str
    properties: Set[str] = field(default_factory=set)
    signals: Set[str] = field(default_factory=set)
    methods: Set[str] = field(default_factory=set)
    base: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "properties": sorted(self.properties),
            "signals": sorted(self.signals),
            "methods": sorted(self.methods),
            "base": self.base,
        }


class ClassRegistry:
    """类名 → ``ClassMeta`` 的元数据注册表 + 反射查询。"""

    def __init__(self) -> None:
        self._classes: Dict[str, ClassMeta] = {}

    # ── 注册 ────────────────────────────────────────────
    def register(
        self,
        cls: Type,
        *,
        properties: Optional[List[str]] = None,
        signals: Optional[List[str]] = None,
        methods: Optional[List[str]] = None,
        base: Optional[str] = None,
    ) -> ClassMeta:
        """注册一个类的元数据；已存在则合并（并集）而非覆盖。"""
        info = self._classes.get(cls.__name__)
        if info is None:
            info = ClassMeta(cls.__name__, base=base)
            self._classes[cls.__name__] = info
        if properties:
            info.properties.update(properties)
        if signals:
            info.signals.update(signals)
        if methods:
            info.methods.update(methods)
        if base is not None:
            info.base = base
        return info

    def register_class(self, *, properties=None, signals=None, methods=None, base=None):
        """装饰器形式注册：``@reg.register_class(properties=[...])``。"""

        def deco(cls: Type) -> Type:
            self.register(
                cls, properties=properties, signals=signals, methods=methods, base=base
            )
            return cls

        return deco

    # ── 查询 ────────────────────────────────────────────
    def has(self, name: str) -> bool:
        return name in self._classes

    def get(self, name: str) -> Optional[ClassMeta]:
        return self._classes.get(name)

    def get_property_names(self, name: str) -> List[str]:
        """返回该类的属性名列表（按名字排序）。未知类返回空列表。"""
        info = self._classes.get(name)
        return sorted(info.properties) if info else []

    def get_signal_names(self, name: str) -> List[str]:
        """返回该类的信号名列表（按名字排序）。未知类返回空列表。"""
        info = self._classes.get(name)
        return sorted(info.signals) if info else []

    def get_method_names(self, name: str) -> List[str]:
        """返回该类的方法名列表（按名字排序）。未知类返回空列表。"""
        info = self._classes.get(name)
        return sorted(info.methods) if info else []

    def get_base(self, name: str) -> Optional[str]:
        info = self._classes.get(name)
        return info.base if info else None

    def ancestors(self, name: str) -> List[str]:
        """沿 ``base`` 链向上收集祖先类（不含自身，由近及远）。"""
        chain: List[str] = []
        current = self.get_base(name)
        seen: Set[str] = set()
        while current and current not in seen:
            chain.append(current)
            seen.add(current)
            current = self.get_base(current)
        return chain

    def list_classes(self) -> List[str]:
        return sorted(self._classes.keys())

    def unregister(self, name: str) -> bool:
        return self._classes.pop(name, None) is not None


#: 进程级默认注册表（类比 Godot 的全局 ClassDB 单例）
default_registry = ClassRegistry()
