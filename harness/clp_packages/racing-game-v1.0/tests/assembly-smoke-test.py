"""
CLP v1.0 Asset Package Smoke Test
==================================

验证 racing-game-v1.0 资产包的完整性：
1. manifest.json 存在且 schema 正确
2. 3 个组件目录存在且包含必需文件
3. evidence 文件存在
4. assembly-graph.json 节点/边数正确
5. matchscore-report.json 评分符合预期
6. 模板文件可读取

运行方式：
    python tests/assembly-smoke-test.py
"""

import json
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).parent.parent
EXPECTED_COMPONENTS = ["audio-manager", "ghost-system", "css-animations"]
REQUIRED_COMPONENT_FILES = [
    "metadata.json",
    "design-physics.json",
    "props-schema.json",
    "template.ts",
    "example-usage.tsx",
]
CSS_REQUIRED_FILES = [
    "metadata.json",
    "design-physics.json",
    "props-schema.json",
    "template.css",
    "keyframes-manifest.json",
    "example-usage.html",
]
EXPECTED_EVIDENCE_FILES = [
    "audio-mapping.json",
    "css-keyframes.json",
    "ghost-architecture.json",
    "source-bundle-hash.txt",
]


def test_manifest_exists():
    manifest_path = PACKAGE_ROOT / "manifest.json"
    assert manifest_path.exists(), f"manifest.json not found at {manifest_path}"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["package_id"] == "racing-game-v1.0"
    assert manifest["version"] == "1.0.0"
    assert len(manifest["components"]) == 3
    print(f"  [PASS] manifest.json valid, {len(manifest['components'])} components")


def test_components_exist():
    for comp_id in EXPECTED_COMPONENTS:
        comp_dir = PACKAGE_ROOT / "components" / comp_id
        assert comp_dir.exists(), f"Component directory missing: {comp_dir}"

        if comp_id == "css-animations":
            required = CSS_REQUIRED_FILES
        else:
            required = REQUIRED_COMPONENT_FILES

        for fname in required:
            fpath = comp_dir / fname
            assert fpath.exists(), f"Required file missing: {fpath}"
        print(f"  [PASS] {comp_id}: {len(required)} files present")


def test_evidence_exists():
    for fname in EXPECTED_EVIDENCE_FILES:
        fpath = PACKAGE_ROOT / "evidence" / fname
        assert fpath.exists(), f"Evidence file missing: {fpath}"
    print(f"  [PASS] {len(EXPECTED_EVIDENCE_FILES)} evidence files present")


def test_assembly_graph():
    graph_path = PACKAGE_ROOT / "assembly-graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    assert len(graph["nodes"]) == 3, f"Expected 3 nodes, got {len(graph['nodes'])}"
    assert len(graph["edges"]) >= 5, f"Expected >=5 edges, got {len(graph['edges'])}"
    assert len(graph["assembly_sequence"]) >= 5
    assert len(graph["cognitive_bus_events"]) >= 3
    print(f"  [PASS] assembly-graph: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges")


def test_matchscore_report():
    report_path = PACKAGE_ROOT / "matchscore-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["aggregate"]["status"] == "all_pass"
    assert report["aggregate"]["matchscore_average"] >= 0.80
    for comp in report["components"]:
        assert comp["weighted_total"] >= 0.80, (
            f"{comp['component_id']} score {comp['weighted_total']} below threshold"
        )
    print(f"  [PASS] matchscore average: {report['aggregate']['matchscore_average']}")


def test_templates_readable():
    for comp_id in EXPECTED_COMPONENTS:
        comp_dir = PACKAGE_ROOT / "components" / comp_id
        if comp_id == "css-animations":
            template = comp_dir / "template.css"
        else:
            template = comp_dir / "template.ts"
        content = template.read_text(encoding="utf-8")
        assert len(content) > 100, f"Template too short: {template}"
    print(f"  [PASS] All 3 templates readable")


def test_keyframes_manifest_count():
    manifest_path = PACKAGE_ROOT / "components" / "css-animations" / "keyframes-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["total_keyframes"] == 22
    assert len(manifest["keyframes"]) == 22
    print(f"  [PASS] keyframes manifest: {manifest['total_keyframes']} animations")


def test_audio_design_physics():
    dp_path = PACKAGE_ROOT / "components" / "audio-manager" / "design-physics.json"
    dp = json.loads(dp_path.read_text(encoding="utf-8"))
    assert len(dp["engine_bands"]) == 18, f"Expected 18 engine bands, got {len(dp['engine_bands'])}"
    assert dp["state_volumes"] == {"off": 0.22, "steady": 0.26, "on": 0.31}
    assert dp["reverb_chain"]["wet_send"] == 0.42
    print(f"  [PASS] audio design-physics: {len(dp['engine_bands'])} bands, reverb config valid")


def main():
    print("=" * 60)
    print("CLP v1.0 Asset Package Smoke Test")
    print(f"Package: {PACKAGE_ROOT.name}")
    print("=" * 60)

    tests = [
        ("Manifest", test_manifest_exists),
        ("Components", test_components_exist),
        ("Evidence", test_evidence_exists),
        ("Assembly Graph", test_assembly_graph),
        ("MatchScore Report", test_matchscore_report),
        ("Templates Readable", test_templates_readable),
        ("Keyframes Count", test_keyframes_manifest_count),
        ("Audio Design Physics", test_audio_design_physics),
    ]

    passed = 0
    failed = 0
    for name, test_fn in tests:
        print(f"\n[{name}]")
        try:
            test_fn()
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {e}")
            failed += 1
        except Exception as e:
            print(f"  [ERROR] {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
