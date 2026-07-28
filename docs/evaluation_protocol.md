# Evaluation protocol

"Working" is not "boxes appear around people." It is:

> The same versioned dataset + the same versioned config + the same code commit
> → reproducible event and runtime metrics.

Run:

```powershell
python scripts/run_benchmark.py --dataset datasets/manifests/eval.yaml --config configs/development.yaml
```

Outputs into `data/benchmark/`: `metrics.json`, `events.csv`,
`false_positives.csv`, `false_negatives.csv`, `performance.csv`, `report.html`.

## Four evaluations

1. **Perception accuracy** — precision/recall/F1/AP50 per class
   ([detection.py](../sentinel/evaluation/detection.py)).
2. **Tracking** — MOTA, id switches, fragmentation, mostly-tracked
   ([tracking.py](../sentinel/evaluation/tracking.py)). HOTA/IDF1 via external
   TrackEval when needed.
3. **Event accuracy** — temporal-IoU matched precision/recall/F1, false alerts
   per camera-hour/day, detection delay, duplicate rate
   ([event_metrics.py](../sentinel/evaluation/event_metrics.py)).
4. **Runtime** — FPS, latency P50/P95/P99, dropped frames, real-time factor
   ([performance.py](../sentinel/evaluation/performance.py)).

## Temporal matching

For ground-truth interval `G=[g_s,g_e]` and predicted `P=[p_s,p_e]`:

$$tIoU = \frac{|G \cap P|}{|G \cup P|}$$

A match requires: same camera **and** same event type **and** `tIoU ≥ 0.3`
(threshold declared before testing, in `configs/*.yaml`).

## MVP performance targets (engineering targets, not guarantees)

| Measure | Target |
| --- | --- |
| Restricted-zone recall / precision | ≥ 0.95 |
| Loitering recall | ≥ 0.90 |
| Collision-risk recall | ≥ 0.85 |
| False alerts | ≤ 1 / camera-day / policy |
| Event creation latency | P95 ≤ 2 s |
| Camera reconnect | ≤ 30 s |
| Dropped frames | ≤ 2% |
| Evidence clip availability | ≥ 99% |

Reproduced on the synthetic benchmark: event P = R = 1.0, 0 false alerts,
P95 detection delay ≈ 0.63 s.

## Reproducibility record

`metrics.json` records: git commit, config environment, thresholds, dataset
hours, per-class detection, tracking, event metrics, and disabled policies.
Real deployments additionally register model version + dataset version in MLflow.

## Benchmark dataset design

See [datasets/README.md](../datasets/README.md) for the manifest format and the
required positive/negative/hard-negative slices.
