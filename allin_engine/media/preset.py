# -*- coding: utf-8 -*-
"""
allin_engine.media.preset —— 媒体子系统的装配预设。
====================================================

补记（2026-09-24）：本模块是**补写的**。`allin_engine/core/profiles.py` 自
J2 S2 起就声明了 media profile（`"media": ["core", "world", "media"]`）并在
`PRESET_FUNCS` 里引用 `preset_media`，但该函数**全仓从未定义** —— 提交
`bd70af2`（2026-09-20，「向内联副本补齐 media 子系统」）补进了 5022 个 media
文件，却**没有改 `core/plugins.py`**，于是 `python -m allin_engine dump-profile`
一直在 `ImportError: cannot import name 'preset_media'` 处硬失败。

装配口径与 `media/README.md` 一致：`media` 服务 = `FormulaEngine` 实例
（dump-profile 显示 `media=FormulaEngine` 服务）。
"""
from __future__ import annotations

from ..core.context import Context

__all__ = ["preset_media"]


def preset_media(ctx: Context) -> Context:
    """媒体子系统层（J2 S2/S3）：公式引擎 + 效果原语 + CA 规则引擎。

    `media` 服务 = `FormulaEngine` 实例（公式编译/模板库，可选依赖 asteval，
    缺失时自动回退纯 Python 求值）。效果原语与 CA 配方为纯函数/数据模块，
    无需注册服务，直接 `from allin_engine.media import ...` 使用。

    幂等：已装则复用；装了但已被卸载则重新装配。无 shutdown/close 钩子，
    故不挂 disposer。
    """
    if ctx.has("media"):
        return ctx
    from allin_engine.media.formula_engine import FormulaEngine

    ctx.provide("media", FormulaEngine())
    return ctx
