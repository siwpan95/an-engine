"""TRPG 数据来源门禁：授权表述不许回退，署名不许丢。

这不是法律检查，是**防止旧表述回流**的机械门禁。三件事：
1. `data.py` 必须写明 SRD 5.1 + CC-BY-4.0（否则署名义务缺依据）；
2. `trpg/` 的 Python 源码里不许再出现"融合……三宝书 / Basic Set"这类说法；
3. 仓库根的 `NOTICE` 必须含官方署名关键词，README 必须指向它。
"""

import importlib.metadata as metadata
import re
from pathlib import Path

from allin_engine.test.runner import skip_unless

ROOT = Path(__file__).resolve().parents[2]
TRPG = ROOT / "allin_engine" / "trpg"

#: 源码仓里 README/NOTICE 在仓库根；装成 wheel 后它们不在 site-packages，
#: 只在 dist-info/licenses/ 里有一份 NOTICE。所以分两种环境取。
_HAS_REPO_DOCS = (ROOT / "README.md").exists() and (ROOT / "NOTICE").exists()
_NO_REPO_DOCS = "README/NOTICE 只在源码仓根；安装环境请查 dist-info（见 NOTICE 定位逻辑）"


def _find_notice():
    """优先仓库根，其次 wheel 的 dist-info/licenses/NOTICE。"""
    local = ROOT / "NOTICE"
    if local.exists():
        return local
    try:
        dist = metadata.distribution("allin-engine")
    except metadata.PackageNotFoundError:
        return None
    for f in dist.files or []:
        if f.name.upper() == "NOTICE":
            cand = Path(dist.locate_file(f))
            if cand.exists():
                return cand
    return None


def test_data_module_declares_srd_and_license():
    text = (TRPG / "data.py").read_text(encoding="utf-8")
    assert "SRD 5.1" in text, "data.py 必须写明数值参照 SRD 5.1"
    assert "CC-BY-4.0" in text, "data.py 必须写明 SRD 5.1 的许可（CC-BY-4.0）"
    assert "NOTICE" in text, "data.py 应指向根 NOTICE"


def test_no_fusion_claims_in_trpg_sources():
    pattern = re.compile(r"融合[^\n]{0,40}(三宝书|Basic Set)")
    offenders = []
    for p in sorted(TRPG.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        if pattern.search(p.read_text(encoding="utf-8", errors="ignore")):
            offenders.append(str(p.relative_to(ROOT)))
    assert not offenders, f"这些文件仍有'融合三宝书/Basic Set'的表述：{offenders}"


def test_notice_has_official_srd_attribution():
    path = _find_notice()
    assert path is not None, "既没有仓库根 NOTICE，也没有 dist-info/licenses/NOTICE"
    notice = path.read_text(encoding="utf-8")
    for needle in ("System Reference Document 5.1", "Wizards of the Coast",
                   "creativecommons.org/licenses/by/4.0"):
        assert needle in notice, f"NOTICE 缺少署名要素：{needle}"


def test_notice_disclaims_gurps_affiliation():
    path = _find_notice()
    assert path is not None
    notice = path.read_text(encoding="utf-8")
    assert "Steve Jackson Games" in notice
    assert "无任何关联" in notice


@skip_unless(_HAS_REPO_DOCS, _NO_REPO_DOCS)
def test_readme_points_to_notice_and_audit():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "NOTICE" in readme
    assert "数据来源.md" in readme


def test_audit_doc_ships_with_package():
    """数据来源登记必须随包分发（package-data 里有 trpg/docs/*.md）。"""
    doc = TRPG / "docs" / "数据来源.md"
    assert doc.exists(), f"登记文档不在包里：{doc}"


def test_audit_doc_covers_every_data_table():
    """登记文档必须点名三张最容易被当成'原表复制'的表。"""
    doc = (TRPG / "docs" / "数据来源.md").read_text(encoding="utf-8")
    for table in ("EQUIPMENT_LIBRARY", "WEAPON_DICE", "SKILL_LIBRARY",
                  "FEATS_LIBRARY", "RACE_TEMPLATES", "BACKGROUNDS"):
        assert table in doc, f"数据来源登记漏了 {table}"
