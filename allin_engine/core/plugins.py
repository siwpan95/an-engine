"""
插件协议与标准预设（preset）
=============================

插件协议（与 Cordis 插件同构，鸭子类型）：

    name  : str                 插件标识
    inject: list[str]           依赖的服务 key（装配期校验，决定加载顺序）
    outer(ctx) -> None|disposer  可选：可重用外作用域，每个父上下文只执行一次
                                 （共享状态/一次性注册；副作用挂父上下文）
    apply(ctx, config) -> None | disposer    注册能力；返回可调用对象则作为统一 disposer

fork 双作用域：ctx.fork_install(plugin) 会把 outer 留在父作用域、
apply 落进每次新建的 fork——同一插件多实例并存、逐实例独立回收。

标准预设（preset）把引擎现有的 add_* 装配改为同一套注册原语：

    preset_core(ctx, update_cb=None)     World + EventBus + 固定步长循环   （对应 add_core）
    preset_world(ctx)                    GameState                          （对应 add_world）
    preset_systems(ctx)                  背包/谜题/命令/存档                 （对应 add_systems）
    preset_combat(ctx)                   卡牌战斗                            （对应 add_combat）
    preset_audio(ctx, backend)           音频系统                            （对应 add_audio）
    preset_ai_brain(ctx, bus=None)       决策大脑（挂入 World 主循环）        （对应 add_ai_brain）
    preset_trpg(ctx)                     TRPG 规则内核（自 D20 并入）          （D&D-GURPS 角色构建）

预设之间用依赖声明组织：preset_world 缺 "world" 时自动先装 preset_core，
依此类推——加载顺序由依赖决定，不再需要手工链式守卫。
所有预设幂等：已装则复用。
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from allin_engine.core.context import Context

__all__ = [
    "preset_core",
    "preset_world",
    "preset_systems",
    "preset_combat",
    "preset_audio",
    "preset_ai_brain",
    "preset_trpg",
    "preset_media",
    "STANDARD_PRESETS",
]


def _shutdown_disposer(obj: Any) -> Optional[Callable[[], Any]]:
    """系统若有 shutdown() 则作为 disposer，否则为 None（销毁时无动作）。"""
    shutdown = getattr(obj, "shutdown", None)
    return shutdown if callable(shutdown) else None


def preset_core(ctx: Context, update_cb: Optional[Callable[[float], None]] = None) -> Context:
    """核心层：World + EventBus + FixedTimestepLoop + WorldLog。幂等：已装则复用。"""
    if ctx.has("world") and ctx.has("bus") and ctx.has("loop") and ctx.has("log"):
        return ctx
    from allin_engine.core.ecs import World
    from allin_engine.core.event_bus import EventBus
    from allin_engine.core.game_loop import FixedTimestepLoop
    from allin_engine.core.world_log import WorldLog

    if not ctx.has("world"):
        ctx.provide("world", World())
    if not ctx.has("bus"):
        ctx.provide("bus", EventBus())
    if not ctx.has("loop"):
        ctx.provide("loop", FixedTimestepLoop(update_cb, None, fixed_dt=1.0 / 60.0))
    if not ctx.has("log"):
        ctx.provide("log", WorldLog())
    return ctx


def preset_world(ctx: Context) -> Context:
    """世界模型层：GameState。缺 core 时自动先装。"""
    if not ctx.has("world"):
        preset_core(ctx)
    if ctx.has("state"):
        return ctx
    from allin_engine.world import GameState
    ctx.provide("state", GameState())
    return ctx


def preset_systems(ctx: Context) -> Context:
    """通用系统层：背包/谜题/命令/存档。缺 core/world 时自动先装。"""
    if not ctx.has("world"):
        preset_core(ctx)
    if not ctx.has("state"):
        preset_world(ctx)
    if ctx.has("inventory") and ctx.has("puzzles") and ctx.has("commands") and ctx.has("saves"):
        return ctx
    from allin_engine.systems import Inventory, PuzzleSystem, CommandHandler, SaveLoadManager
    from allin_engine.core.paths import get_save_dir

    bus = ctx.get("bus")
    inventory = Inventory()
    puzzles = PuzzleSystem(event_bus=bus)
    commands = CommandHandler()
    saves = SaveLoadManager(save_dir=get_save_dir())
    ctx.provide("inventory", inventory, dispose=_shutdown_disposer(inventory))
    ctx.provide("puzzles", puzzles, dispose=_shutdown_disposer(puzzles))
    ctx.provide("commands", commands, dispose=_shutdown_disposer(commands))
    ctx.provide("saves", saves, dispose=_shutdown_disposer(saves))
    return ctx


def preset_combat(ctx: Context) -> Context:
    """卡牌战斗层。缺 core/world 时自动先装。"""
    if not ctx.has("world"):
        preset_core(ctx)
    if not ctx.has("state"):
        preset_world(ctx)
    if ctx.has("card_library") and ctx.has("enemy_library") and ctx.has("combat"):
        return ctx
    from allin_engine.systems.combat import CardLibrary, EnemyLibrary, CombatEngine

    card_library = CardLibrary()
    enemy_library = EnemyLibrary()
    combat = CombatEngine()
    ctx.provide("card_library", card_library, dispose=_shutdown_disposer(card_library))
    ctx.provide("enemy_library", enemy_library, dispose=_shutdown_disposer(enemy_library))
    ctx.provide("combat", combat, dispose=_shutdown_disposer(combat))
    return ctx


def preset_audio(ctx: Context, backend: str = "pygame") -> Context:
    """音频系统。backend: 'pygame' | 'bloodmusic'。"""
    if ctx.has("audio"):
        return ctx
    from allin_engine.audio import AudioSystem

    audio = AudioSystem(backend=backend)
    ctx.provide("audio", audio, dispose=_shutdown_disposer(audio))
    return ctx


def preset_ai_brain(ctx: Context, event_bus: Any = None) -> Context:
    """决策/行为大脑：BrainSystem 挂入 World 主循环。缺 core 时自动先装。"""
    if not ctx.has("world"):
        preset_core(ctx)
    if ctx.has("brain"):
        return ctx
    from allin_engine.ai import BrainSystem

    bus = event_bus if event_bus is not None else ctx.get("bus")
    brain = BrainSystem(event_bus=bus)
    ctx.get("world").add_system(brain)
    ctx.provide("brain", brain, dispose=_shutdown_disposer(brain))
    return ctx


def preset_trpg(ctx: Context) -> Context:
    """TRPG 规则内核层（自 D20 并入，R2）：D&D-GURPS 变体角色构建内核。

    14 个子系统（属性/装备/优缺点/天赋/技术/种族/背景/专长/技能/骰子/衍生/
    法术位/休整/战斗宏/角色卡）+ 数据中枢。缺 'bus' 时提供独立 EventBus；
    'trpg' 服务 = TrpgContext 适配器，其 effect 栈挂宿主（注册即回滚）。
    幂等：已装且存活则复用。装配实现见 allin_engine.trpg.preset。
    """
    from allin_engine.trpg import preset_trpg as _preset

    return _preset(ctx)


def preset_media(ctx: Context) -> Context:
    """媒体子系统层（J2 S2/S3）：公式引擎 + 效果原语 + CA 规则引擎。

    'media' 服务 = FormulaEngine 实例（公式编译/模板库）。效果原语与 CA 配方
    为纯函数/数据模块，无需注册。幂等：已装则复用。装配实现见
    allin_engine.media.preset。

    补记（2026-09-24）：本函数为**补写**。core/profiles.py 自 J2 S2 起就引用
    preset_media，但 bd70af2（2026-09-20）补进 media 文件时漏改本文件，
    导致 `python -m allin_engine dump-profile` 一直 ImportError 硬失败。
    """
    from allin_engine.media.preset import preset_media as _preset

    return _preset(ctx)


#: 标准预设索引（供 --dump-profile 与 preset 装配使用）
STANDARD_PRESETS = {
    "core": preset_core,
    "world": preset_world,
    "systems": preset_systems,
    "combat": preset_combat,
    "audio": preset_audio,
    "ai_brain": preset_ai_brain,
    "trpg": preset_trpg,
    "media": preset_media,
}


# ============================================================
# 插件钩子 ABI（hookspec / hookimpl / PluginManager）
# ============================================================
#
# 来源：pluggy（思路档，MIT）。
# 借用范围：**思路**（自研实现「钩子规范 + 实现收集 + 按权重排序调用」概念，
# 未搬 pluggy 源码、未照抄其命名 / 结构）。
#
# 设计：用 ``@hookspec`` 标记"钩子规范"（定义有哪些扩展点），用 ``@hookimpl``
# 标记"钩子实现"并带 ``weight``；``PluginManager`` 收集所有实现后，按 hook 名
# 索引、按 weight 降序调用。语义对齐 pluggy 的「先注册规范、再注册插件、按序调用」。


class _HookSpec:
    """钩子规范标记。"""

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name


class _HookImpl:
    """钩子实现标记。"""

    __slots__ = ("func", "weight")

    def __init__(self, func: Callable, weight: int) -> None:
        self.func = func
        self.weight = weight


def hookspec(func: Optional[Callable] = None, *, name: Optional[str] = None):
    """标记函数为钩子规范（hook specification）。

    用法::
        @hookspec
        def calculate_damage(ctx, raw): ...
        # 或指定名称
        @hookspec(name="on_damage")
        def _calc(ctx, raw): ...
    """

    def decorate(f: Callable) -> Callable:
        f._hookspec = _HookSpec(name or f.__name__)  # type: ignore[attr-defined]
        return f

    if func is None:
        return decorate
    return decorate(func)


def hookimpl(func: Optional[Callable] = None, *, weight: int = 0):
    """标记函数为钩子实现（hook implementation）。``weight`` 越大越先调用。

    用法::
        @hookimpl(weight=10)
        def calculate_damage(ctx, raw): return raw * 2
    """

    def decorate(f: Callable) -> Callable:
        f._hookimpl = _HookImpl(f, weight)  # type: ignore[attr-defined]
        return f

    if func is None:
        return decorate
    return decorate(func)


class PluginManager:
    """收集钩子实现并按权重排序调用的插件管理器（pluggy 风格自研）。"""

    def __init__(self, project_name: str = "anonymous") -> None:
        self.project_name = project_name
        # hook 名 -> 实现列表（已按 weight 降序）
        self._impls: Dict[str, List[_HookImpl]] = {}
        # hook 名 -> 规范
        self._specs: Dict[str, _HookSpec] = {}

    # ── 规范 / 插件注册 ────────────────────────────────
    def add_hookspecs(self, module_or_cls: Any) -> "PluginManager":
        """从一个模块或类上收集所有 ``@hookspec`` 作为钩子规范。"""
        for name in dir(module_or_cls):
            attr = getattr(module_or_cls, name)
            spec = getattr(attr, "_hookspec", None)
            if spec is not None:
                self._specs[spec.name] = spec
        return self

    @staticmethod
    def _resolve_hookimpl(attr: Any) -> Optional[_HookImpl]:
        """从属性（函数或绑定方法）上解析 ``@hookimpl`` 标记。

        绑定方法不会转发底层函数的自定义属性，所以多探一层 ``__func__``。
        """
        impl = getattr(attr, "_hookimpl", None)
        if impl is None:
            underlying = getattr(attr, "__func__", None)
            if underlying is not None:
                impl = getattr(underlying, "_hookimpl", None)
        return impl

    @staticmethod
    def _underlying(func: Callable) -> Callable:
        """取出底层函数对象，用于跨访问的身份匹配（每次访问方法会新建绑定方法）。"""
        return getattr(func, "__func__", func)

    def register(self, plugin: Any) -> "PluginManager":
        """从一个模块或实例上收集所有 ``@hookimpl`` 实现并登记。

        实例方法会保留绑定（调用时自动传入 self）；排序按 weight 降序。
        """
        for name in dir(plugin):
            attr = getattr(plugin, name)
            impl = self._resolve_hookimpl(attr)
            if impl is not None:
                self._impls.setdefault(attr.__name__, []).append(_HookImpl(attr, impl.weight))
                self._impls[attr.__name__].sort(key=lambda i: i.weight, reverse=True)
        return self

    def unregister(self, plugin: Any) -> "PluginManager":
        """注销一个模块/实例上带 ``@hookimpl`` 的实现。"""
        for name in dir(plugin):
            attr = getattr(plugin, name)
            impl = self._resolve_hookimpl(attr)
            if impl is not None:
                key = self._underlying(attr)
                lst = self._impls.get(attr.__name__)
                if lst is not None:
                    self._impls[attr.__name__] = [
                        i for i in lst if self._underlying(i.func) is not key
                    ]
                    if not self._impls[attr.__name__]:
                        del self._impls[attr.__name__]
        return self

    # ── 调用 ────────────────────────────────────────────
    def get_hookcaller(self, name: str) -> Callable[..., List[Any]]:
        """返回可调用对象：调用即按 weight 降序执行所有实现，返回结果列表。"""
        impls = self._impls.get(name, [])

        def call(*args: Any, **kwargs: Any) -> List[Any]:
            results: List[Any] = []
            for impl in impls:
                results.append(impl.func(*args, **kwargs))
            return results

        return call

    @property
    def hook(self) -> "_HookNamespace":
        """动态访问 ``pm.hook.<name>(...)``，调用对应钩子的全部实现。"""
        return _HookNamespace(self)

    def has_hook(self, name: str) -> bool:
        return name in self._impls and bool(self._impls[name])


class _HookNamespace:
    """``pm.hook.<name>`` 的动态命名空间。"""

    def __init__(self, pm: PluginManager) -> None:
        self._pm = pm

    def __getattr__(self, name: str) -> Callable[..., List[Any]]:
        return self._pm.get_hookcaller(name)
