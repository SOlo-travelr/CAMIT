# Event definitions

All four MVP events are deterministic functions of `TrackObservation` streams.

## Restricted-zone entry

State machine per (policy, zone, track):

```
OUTSIDE → PENDING_ENTRY → INSIDE → PENDING_EXIT → OUTSIDE
```

- Ground-contact point = bottom-center of the box.
- Fires only on a **stable** outside→inside transition.
- `minimum_duration_ms` debounces single-frame boundary jitter.
- `cooldown_seconds` suppresses repeats.

Implementation: [sentinel/events/restricted_zone.py](../sentinel/events/restricted_zone.py).

## Loitering

```
loitering_duration = now − first_stable_entry_time
```

- Tolerates tracking gaps up to `max_tracking_gap_seconds` (default 1.5 s).
- Resets on zone exit or an over-long gap.
- Fires once per dwell episode (cooldown-gated).

Implementation: [sentinel/events/loitering.py](../sentinel/events/loitering.py).

## Pedestrian–vehicle proximity (requires calibration)

`d(t) = ‖p_person(t) − p_vehicle(t)‖₂` in metric ground coordinates.

Triggers only when both tracks have sufficient history, the vehicle is moving
above a speed threshold, and the distance stays below threshold for several
consecutive updates.

Implementation: [sentinel/events/proximity.py](../sentinel/events/proximity.py).

## Predicted collision risk (requires calibration)

Constant-velocity projection over horizon `H`:

$$\mathbf{r} = \mathbf{p}_p - \mathbf{p}_v,\quad \mathbf{u} = \mathbf{v}_p - \mathbf{v}_v$$
$$t^{*} = \mathrm{clip}\!\left(-\frac{\mathbf{r}\cdot\mathbf{u}}{\lVert\mathbf{u}\rVert^{2}+\epsilon},\,0,\,H\right),\quad d_{\min} = \lVert \mathbf{r} + t^{*}\mathbf{u}\rVert$$

Initial rule:

```
high_risk = predicted_min_distance_m < 1.0
        and time_to_closest_approach_s < 2.0
        and vehicle_speed_mps > 0.5
```

A calibrated logistic score can replace the boolean later without changing the
interface. Implementation: [sentinel/events/collision_risk.py](../sentinel/events/collision_risk.py).

## Monocular distance limitation

A single camera does not inherently provide metric distance. Metric rules
(proximity, collision) are **disabled** for a camera until a planar homography
calibration with acceptable reprojection error exists. See
[docs/evaluation_protocol.md](evaluation_protocol.md).
