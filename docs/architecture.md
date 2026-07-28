# Architecture

Sentinel is an edge-capable video-intelligence platform for industrial safety.
It is deliberately **not** an overbuilt multi-agent system: the runtime is a
deterministic pipeline with modular perception adapters, a stateful event
engine, incident evidence generation, evaluation tooling, and an **optional**
natural-language policy translator.

## Layers

```
Operator Web App  ── REST/WebSocket ──►  API Service
                                            │
        ┌───────────────────────────────────┼───────────────────────────┐
        ▼                                   ▼                           ▼
 NL Policy Translator (LLM optional)   Incident Service           Event Engine
                                            ▲                           ▲
                                            │  events                   │ observations
                                            └───────────────────  Perception Pipeline
                                                                        ▲ frames
                                                                  Video Ingestion
```

Storage: PostgreSQL (metadata) · object storage (clips/snapshots) · Redis
(live state/queues, optional) · MLflow (experiments, optional).

## The deterministic real-time path

```
decode → sample → detect → track → observe → evaluate rules → emit event → incident
```

It keeps functioning when the LLM, internet, dashboard, or an alert integration
is unavailable. No LLM call ever happens inside the frame loop.

### LLM boundary (PHIA pattern)

The LLM may only: translate NL → policy JSON, request missing policy fields,
explain why an event fired, summarise incident timelines, and search structured
records. It must never assign track IDs, compute distances, decide zone
geometry, invent observations, trigger emergency actions, override thresholds,
or analyse every frame.

## Package map

| Package | Responsibility |
| --- | --- |
| [sentinel/video](../sentinel/video) | RTSP/file/webcam sources, sampling, ring buffer |
| [sentinel/perception](../sentinel/perception) | detector + tracker interfaces, calibration, observations |
| [sentinel/events](../sentinel/events) | geometry, state machines, the four event rules, engine |
| [sentinel/policies](../sentinel/policies) | restricted schema, validator, compiler, translator |
| [sentinel/incidents](../sentinel/incidents) | dedup manager, clip writer, snapshot, explanation |
| [sentinel/storage](../sentinel/storage) | ORM models, repositories, object store |
| [sentinel/evaluation](../sentinel/evaluation) | detection/tracking/event/runtime metrics, benchmark |
| [apps/api](../apps/api) | FastAPI service |
| [apps/worker](../apps/worker) | camera pipeline runtime + watchdog |

## Data contracts

Defined in [sentinel/contracts.py](../sentinel/contracts.py): `FramePacket`,
`BoundingBox`, `Detection`, `TrackObservation`, `EventCandidate`, `Incident`,
`IncidentEvidence`, `OperatorFeedback`, `ModelVersion`, `EvaluationRun`.
Ground-contact point for people/vehicles is the **bottom-center** of the box.

## <a id="phases"></a>Development phases

0. Foundation — packaging, config, docker-compose, logging, health. ✅
1. Recorded-video perception — detector/tracker adapters, benchmark FPS. ✅
2. Zones + event engine — restricted entry, loitering, dedup, geometry tests. ✅
3. Incident evidence — ring buffer, clips, snapshots, DB records, API. ✅
4. Calibration + risk — homography, velocity, proximity, collision risk. ✅
5. Evaluation — manifest, temporal-IoU matching, per-slice + runtime report. ✅
6. Policy translator — NL → schema-validated JSON, no code execution. ✅ (LLM optional)
7. Live RTSP pilot — reconnect, watchdog, shadow mode, soak test. ▶ scaffolding in place
