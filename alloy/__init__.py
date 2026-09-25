"""alloy —— 向后兼容别名包（引擎旧名 → `allin_engine`）

为什么存在
----------
统一引擎历史上叫 **alloy**，后改名为 **allin_engine**（PyPI 分发名 `allin-engine`）。
改名时下游已有代码按旧名 `alloy.*` 写死导入，典型受害者是 **`siwpan/d20`**：
它是"规则界面壳"，声明"老 API 100% 不变"，其全部 5 个 shim 文件都写
`from alloy.trpg... import ...`。引擎改名后这些导入全部失效 —— **d20 整个不可用**。

修复方式的选择（2026-09-25，与用户"独立仓 + 导入适配"的口径一致）
----------------------------------------------------------------
· 方案 A：改 d20 的 5 个 shim 文件 → 要动下游 5 处，且下游每加一处 `alloy` 导入都要再改。
· 方案 B（**采用**）：在引擎侧提供 `alloy` 兼容别名 → **改 1 处**，下游零改动，
  且"旧名仍可用"这一契约被真正兑现，而不是把兼容责任推给每个下游。

本模块**不做任何逻辑**，只把 `allin_engine` 的对外面在旧名空间下重新导出；
`alloy.trpg` 指向真正的规范落点 `allin_engine.trpg`。

若将来决定彻底废弃旧名，删掉本包并同步下游即可（届时 grep `alloy` 即得全部引用点）。
"""
import importlib
import sys

import allin_engine as _engine

__version__ = getattr(_engine, "__version__", "0.0.0")
__doc__ = (_engine.__doc__ or "")  # noqa: A001  沿用引擎自身的模块说明

# 1) 让 `alloy.trpg` 能解析：注册子模块别名
#    注意必须指向**规范落点** allin_engine.trpg（含完整 trpg 子系统实现），
#    而不是仓根那个遗留的 trpg/ 目录。
_trpg = importlib.import_module("allin_engine.trpg")
sys.modules[__name__ + ".trpg"] = _trpg

# 2) 把引擎顶层对外名字在旧名空间下重导出（不含下划线开头的私有名）
for _n in dir(_engine):
    if not _n.startswith("_"):
        globals()[_n] = getattr(_engine, _n)
globals()["trpg"] = _trpg

__all__ = [n for n in dir(_engine) if not n.startswith("_")] + ["trpg"]
