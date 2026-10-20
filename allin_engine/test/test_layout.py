"""布局不变量 —— 防止「双写镜像」复活。

背景（2026-10-20 诊断）：
本仓曾把**整个仓库根**复制进 ``allin_engine/`` 以便发 PyPI，之后代码靠
「人工双写」维持两份一致（每次改动同时写 ``X`` 与 ``allin_engine/X``）。
结果是 5,139 个文件两份跟踪、近 5,000 个 media JSON 进了两次库。

收口后只保留**单一布局**：代码全在 ``allin_engine/``，仓库根只放发行与治理文件。
本模块把这条决定钉成机械门禁：谁再把文件写到根侧镜像位，测试当场变红。
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: 仓库根不允许出现的镜像目录（代码只许放 allin_engine/ 下）
FORBIDDEN_ROOT_DIRS = (
    "core", "world", "systems", "render", "audio", "fx",
    "ai", "media", "trpg", "test", "utils",
)

#: 仓库根不允许出现的镜像入口（旧平铺布局的包入口）
FORBIDDEN_ROOT_FILES = (
    "__init__.py", "__main__.py", "cli.py",
    "example_quickstart.py", "example_local_font.py", "example_decision_ai.py",
)

#: 包目录内不允许出现的「根文件化石」（它们是整仓复制时的残留）
FORBIDDEN_PKG_FOSSILS = (
    "pyproject.toml", "README.md", "LICENSE", "requirements.txt", ".gitignore", ".github",
)


def _in_repo() -> bool:
    """装到 site-packages 里跑时不适用（那里没有仓库根）。"""
    return (REPO_ROOT / "pyproject.toml").exists() and (REPO_ROOT / "allin_engine").is_dir()


def test_no_root_mirror_dirs():
    """仓库根不得再出现 core/ world/ systems/ … 这些镜像目录。"""
    if not _in_repo():
        return
    offenders = [d for d in FORBIDDEN_ROOT_DIRS if (REPO_ROOT / d).exists()]
    assert not offenders, (
        f"仓库根出现镜像目录 {offenders}：双写布局已下线，代码只放 allin_engine/ 下"
    )


def test_no_root_mirror_files():
    """仓库根不得再出现旧平铺布局的包入口与示例。"""
    if not _in_repo():
        return
    offenders = [f for f in FORBIDDEN_ROOT_FILES if (REPO_ROOT / f).exists()]
    assert not offenders, (
        f"仓库根出现镜像文件 {offenders}：包入口只在 allin_engine/ 内"
    )


def test_no_root_file_fossils_in_package():
    """allin_engine/ 内不得再夹带仓库根文件的副本。"""
    if not _in_repo():
        return
    pkg = REPO_ROOT / "allin_engine"
    offenders = [f for f in FORBIDDEN_PKG_FOSSILS if (pkg / f).exists()]
    assert not offenders, (
        f"allin_engine/ 内出现仓库根文件副本 {offenders}：它们不随包分发，也不该入库"
    )


def test_packages_find_still_scoped():
    """打包范围必须仍是 allin_engine* + alloy*（防止有人为了让根侧合法而放宽）。"""
    if not _in_repo():
        return
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'include = ["allin_engine*", "alloy*"]' in text, (
        "pyproject.toml 的 [tool.setuptools.packages.find] include 已偏离 "
        '["allin_engine*", "alloy*"]，请确认没有把根侧镜像重新纳入打包范围'
    )
