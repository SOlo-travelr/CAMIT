# Privacy

This platform processes footage of people at work. Treat all footage and
derived data as sensitive.

## Principles

- **Purpose limitation** — MVP scope is industrial safety only. No face
  recognition, emotion recognition, cross-camera identity, or weapon/fight
  detection. These are explicitly out of scope.
- **Data minimisation** — PostgreSQL stores metadata only. Store high-frequency
  observations at a reduced rate (2–5 / s / track) with configurable retention.
  Never store every frame in the database.
- **Evidence scoping** — clips/snapshots are generated only for fired incidents,
  covering a bounded pre/post window. Raw vs annotated variants are saved subject
  to the site privacy policy.
- **Retention** — configure object-storage lifecycle rules per site; incident
  evidence should expire on a defined schedule.
- **Access control** — API access must be authenticated and audited (wire your
  IdP into `apps/api`). Incident review is role-gated.
- **Human in the loop** — `review.human_confirmation_required` keeps a person in
  the decision path; operator feedback is stored for **offline** evaluation only
  and never mutates live thresholds automatically.

## Operator feedback

Feedback verdicts feed an offline dataset, not production thresholds. See
[docs/evaluation_protocol.md](evaluation_protocol.md).
