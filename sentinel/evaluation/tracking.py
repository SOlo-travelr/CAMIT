"""Basic multi-object tracking metrics (identity switches, MOTA, fragmentation).

Full HOTA/IDF1 are provided by external tools (e.g. TrackEval); here we compute
lightweight, dependency-free approximations useful for CI regression checks.
"""

from __future__ import annotations

from dataclasses import dataclass

from sentinel.contracts import BoundingBox


@dataclass
class TrackingMetrics:
    mota: float
    id_switches: int
    fragmentations: int
    mostly_tracked: int
    false_positives: int
    misses: int


def evaluate_tracking(
    frames: list[tuple[list[tuple[int, BoundingBox]], list[tuple[int, BoundingBox]]]],
    iou_threshold: float = 0.5,
) -> TrackingMetrics:
    """Evaluate tracking across frames.

    Each frame is (predicted [(track_id, box)], ground_truth [(gt_id, box)]).
    """
    gt_to_pred: dict[int, int] = {}
    id_switches = 0
    fragmentations = 0
    fp = 0
    misses = 0
    total_gt = 0
    gt_seen_frames: dict[int, int] = {}
    gt_matched_frames: dict[int, int] = {}
    gt_last_matched: dict[int, bool] = {}

    for preds, gts in frames:
        total_gt += len(gts)
        used_pred: set[int] = set()
        for gid, gbox in gts:
            gt_seen_frames[gid] = gt_seen_frames.get(gid, 0) + 1
            best_iou, best_pid = 0.0, None
            for pid, pbox in preds:
                if pid in used_pred:
                    continue
                iou = gbox.iou(pbox)
                if iou > best_iou:
                    best_iou, best_pid = iou, pid
            if best_iou >= iou_threshold and best_pid is not None:
                used_pred.add(best_pid)
                gt_matched_frames[gid] = gt_matched_frames.get(gid, 0) + 1
                if gid in gt_to_pred and gt_to_pred[gid] != best_pid:
                    id_switches += 1
                gt_to_pred[gid] = best_pid
                if not gt_last_matched.get(gid, True):
                    fragmentations += 1
                gt_last_matched[gid] = True
            else:
                misses += 1
                gt_last_matched[gid] = False
        fp += len(preds) - len(used_pred)

    mostly_tracked = sum(
        1
        for gid, seen in gt_seen_frames.items()
        if gt_matched_frames.get(gid, 0) / seen >= 0.8
    )
    mota = 1.0 - (misses + fp + id_switches) / total_gt if total_gt else 0.0
    return TrackingMetrics(
        mota=round(mota, 4),
        id_switches=id_switches,
        fragmentations=fragmentations,
        mostly_tracked=mostly_tracked,
        false_positives=fp,
        misses=misses,
    )
