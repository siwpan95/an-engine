"""
兼容 shim：allin_engine → alloy（引擎改名过渡期，2026-08-23）。

本包只做一件事：把对旧名 allin_engine 的导入重定向到新名 alloy，
并保证子模块（allin_engine.core / allin_engine.systems / ...）与
alloy 同名模块是**同一个模块对象**（类身份一致，避免 entity.get()
之类的身份错乱）。

迁移完成后（全仓库引用清零）可整体删除本目录。
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import warnings

_PREFIX = "allin_engine"
_REAL = "alloy"

warnings.warn(
    f"'{_PREFIX}' 已改名为 '{_REAL}'，请把导入迁移为 'from {_REAL} import ...'。"
    "本 shim 仅作过渡，迁移完成后将删除。",
    DeprecationWarning,
    stacklevel=2,
)


class _ShimLoader:
    """把 allin_engine[.X] 的加载委托给 alloy[.X]，并做 sys.modules 别名。"""

    def __init__(self, real_name: str):
        self._real = real_name

    def create_module(self, spec):
        module = importlib.import_module(self._real)
        sys.modules[spec.name] = module
        return module

    def exec_module(self, module):
        pass  # 真实模块已经执行过


class _ShimFinder:
    def find_spec(self, fullname, path=None, target=None):
        if fullname != _PREFIX and not fullname.startswith(_PREFIX + "."):
            return None
        real = _REAL + fullname[len(_PREFIX):]
        if real in sys.modules:
            return importlib.util.spec_from_loader(fullname, _ShimLoader(real))
        try:
            real_spec = importlib.util.find_spec(real)
        except (ImportError, AttributeError, ValueError):
            return None
        if real_spec is None:
            return None
        # 注：不带 origin/submodule_search_locations —— 子模块同样由本
        # finder 拦截（meta_path 优先于父包 __path__），无需包级搜索路径。
        return importlib.util.spec_from_loader(fullname, _ShimLoader(real))


if not any(isinstance(f, _ShimFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _ShimFinder())

# 立即把本包名指向真实 alloy 包
try:
    real_pkg = importlib.import_module(_REAL)
    sys.modules[__name__] = real_pkg
except Exception:  # alloy 不存在时保留本 shim 自身，导入会报更清晰的错误
    pass
