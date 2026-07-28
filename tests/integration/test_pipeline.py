"""Integration test: full offline pipeline via the benchmark on synthetic data.

Runs generate_test_videos + run_benchmark and asserts the platform meets its
MVP event targets, proving reproducibility from a versioned manifest + config.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sentinel.config import load_config
from sentinel.evaluation.benchmark import run_benchmark

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    from scripts.generate_test_videos import SCENARIOS, render_scenario, write_manifest

    out = tmp_path_factory.mktemp("videos")
    entries = []
    for factory in SCENARIOS:
        scenario = factory()
        vp, sp = render_scenario(scenario, out)
        entries.append((scenario.name, vp, sp))
    manifest = out / "eval.yaml"
    write_manifest(entries, manifest)
    # Rewrite policies_dir to absolute so the test is CWD-independent.
    import yaml

    data = yaml.safe_load(manifest.read_text())
    data["policies_dir"] = str(ROOT / "configs" / "policies")
    manifest.write_text(yaml.safe_dump(data), encoding="utf-8")
    return manifest


def test_pipeline_meets_event_targets(generated, tmp_path):
    config = load_config(ROOT / "configs" / "development.yaml")
    metrics = run_benchmark(generated, config, tmp_path / "bench")
    ev = metrics["events"]

    assert ev["recall"] == 1.0
    assert ev["precision"] == 1.0
    assert ev["false_negatives"] == 0
    assert ev["false_positives"] == 0
    assert ev["p95_detection_delay_s"] <= 2.0
    assert metrics["tracking"]["id_switches"] == 0
    # Output artifacts exist and are reproducible.
    for name in ("metrics.json", "events.csv", "false_positives.csv", "report.html"):
        assert (tmp_path / "bench" / name).exists()
