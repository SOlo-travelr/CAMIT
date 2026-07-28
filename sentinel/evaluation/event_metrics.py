"""Event-level metrics with temporal IoU matching.

Frame accuracy is not the goal; incidents are matched to ground-truth event
intervals by camera + event type + temporal IoU. Reports precision/recall/F1,
false-alert rates, detection delay and duplicate rate.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EventInterval:
    camera_id: str
    event_type: str
    start_s: float
    end_s: float
    track_ids: tuple[int, ...] = ()


def temporal_iou(a: EventInterval, b: EventInterval) -> float:
    inter = max(0.0, min(a.end_s, b.end_s) - max(a.start_s, b.start_s))
    union = (a.end_s - a.start_s) + (b.end_s - b.start_s) - inter
    return inter / union if union > 0 else 0.0


@dataclass
class EventMetrics:
    precision: float
    recall: float
    f1: float
    true_positives: int
    false_positives: int
    false_negatives: int
    duplicate_alerts: int
    false_alerts_per_camera_hour: float
    false_alerts_per_camera_day: float
    median_detection_delay_s: float
    p95_detection_delay_s: float
    matched: list[tuple] = field(default_factory=list)
    false_positive_list: list[EventInterval] = field(default_factory=list)
    false_negative_list: list[EventInterval] = field(default_factory=list)


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def evaluate_events(
    predicted: list[EventInterval],
    ground_truth: list[EventInterval],
    iou_threshold: float = 0.3,
    total_camera_hours: float = 1.0,
) -> EventMetrics:
    matched_gt: set[int] = set()
    matched_pred: set[int] = set()
    matches: list[tuple] = []
    delays: list[float] = []
    duplicates = 0

    # Sort predictions by start so earliest wins the match (best delay).
    pred_order = sorted(range(len(predicted)), key=lambda i: predicted[i].start_s)
    for pi in pred_order:
        p = predicted[pi]
        best_iou, best_gi = 0.0, -1
        for gi, g in enumerate(ground_truth):
            if g.camera_id != p.camera_id or g.event_type != p.event_type:
                continue
            iou = temporal_iou(p, g)
            if iou > best_iou:
                best_iou, best_gi = iou, gi
        if best_iou >= iou_threshold and best_gi >= 0:
            if best_gi in matched_gt:
                duplicates += 1
                matched_pred.add(pi)  # still not a new TP
                continue
            matched_gt.add(best_gi)
            matched_pred.add(pi)
            matches.append((pi, best_gi, round(best_iou, 3)))
            delay = max(0.0, p.start_s - ground_truth[best_gi].start_s)
            delays.append(delay)

    tp = len(matched_gt)
    fp = len(predicted) - len(matched_pred)
    fn = len(ground_truth) - len(matched_gt)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    fp_per_hour = fp / total_camera_hours if total_camera_hours else 0.0
    return EventMetrics(
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        duplicate_alerts=duplicates,
        false_alerts_per_camera_hour=round(fp_per_hour, 4),
        false_alerts_per_camera_day=round(fp_per_hour * 24, 4),
        median_detection_delay_s=round(_percentile(delays, 0.5), 4),
        p95_detection_delay_s=round(_percentile(delays, 0.95), 4),
        matched=matches,
        false_positive_list=[predicted[i] for i in range(len(predicted)) if i not in matched_pred],
        false_negative_list=[ground_truth[i] for i in range(len(ground_truth)) if i not in matched_gt],
    )
