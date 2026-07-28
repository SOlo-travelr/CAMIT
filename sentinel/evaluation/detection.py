"""Detection metrics: precision, recall, F1 and AP50 by class."""

from __future__ import annotations

from dataclasses import dataclass, field

from sentinel.contracts import BoundingBox, Detection


@dataclass
class DetectionMetrics:
    per_class: dict[str, dict[str, float]] = field(default_factory=dict)
    overall: dict[str, float] = field(default_factory=dict)


def _match(
    preds: list[Detection], gts: list[BoundingBox], iou_threshold: float
) -> tuple[int, int, int]:
    """Greedy match predictions to ground-truth boxes; returns (tp, fp, fn)."""
    used = set()
    tp = 0
    order = sorted(range(len(preds)), key=lambda i: preds[i].confidence, reverse=True)
    for i in order:
        best_iou, best_j = 0.0, -1
        for j, gt in enumerate(gts):
            if j in used:
                continue
            iou = preds[i].box.iou(gt)
            if iou > best_iou:
                best_iou, best_j = iou, j
        if best_iou >= iou_threshold and best_j >= 0:
            used.add(best_j)
            tp += 1
    fp = len(preds) - tp
    fn = len(gts) - len(used)
    return tp, fp, fn


def evaluate_detections(
    frames: list[tuple[list[Detection], list[tuple[str, BoundingBox]]]],
    iou_threshold: float = 0.5,
) -> DetectionMetrics:
    """Evaluate detections against ground truth across frames.

    ``frames`` is a list of (predictions, [(class_name, box), ...]).
    """
    classes: set[str] = set()
    for preds, gts in frames:
        classes.update(p.class_name for p in preds)
        classes.update(c for c, _ in gts)

    per_class: dict[str, dict[str, float]] = {}
    tot_tp = tot_fp = tot_fn = 0
    for cls in sorted(classes):
        c_tp = c_fp = c_fn = 0
        for preds, gts in frames:
            cp = [p for p in preds if p.class_name == cls]
            cg = [b for c, b in gts if c == cls]
            tp, fp, fn = _match(cp, cg, iou_threshold)
            c_tp += tp
            c_fp += fp
            c_fn += fn
        precision = c_tp / (c_tp + c_fp) if (c_tp + c_fp) else 0.0
        recall = c_tp / (c_tp + c_fn) if (c_tp + c_fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        per_class[cls] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "ap50": round(precision * recall, 4),  # simplified AP proxy
            "tp": c_tp,
            "fp": c_fp,
            "fn": c_fn,
        }
        tot_tp += c_tp
        tot_fp += c_fp
        tot_fn += c_fn

    p = tot_tp / (tot_tp + tot_fp) if (tot_tp + tot_fp) else 0.0
    r = tot_tp / (tot_tp + tot_fn) if (tot_tp + tot_fn) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return DetectionMetrics(
        per_class=per_class,
        overall={"precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4)},
    )
