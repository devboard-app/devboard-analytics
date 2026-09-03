# devboard-analytics

The activity log for DevBoard, and eventually the reports built on top of it.

It consumes the `devboard:events` Redis stream, translates each event into a typed
`ActivityEvent`, and stores it in MongoDB. Every service that publishes to the stream ends
up here, which makes this collection the closest thing DevBoard has to a system of record
for "what happened".

FastAPI + Motor + MongoDB + Redis Streams. Port **8006**.

## Why this is one service and not two

The original design had Django core writing an activity log into `core_db`, with a
separate read-only FastAPI service computing reports off it. That doesn't survive contact
with a second publisher: `ticket.commit_linked` originates in devboard-integrations, not
core, and core has no business owning a table it doesn't write.

So the log lives in its own service, with its own store, and anything that wants to record
activity publishes to the stream. Reports are computed in the same service because they
read nothing but this collection.

Mongo rather than Postgres because event metadata genuinely varies by action — a label
event and a commit event have nothing in common but the envelope. The rest of DevBoard is
Postgres; this is the one place where a document store earns its keep.

## Two processes, one image

| container | command | role |
|---|---|---|
| `devboard-analytics` | `uvicorn app.main:app` | HTTP API |
| `devboard-analytics-worker` | `python -m app.consumer.worker` | stream consumer |

The worker does not build the FastAPI app — it calls `connect_to_mongo()` directly. Both
call `ensure_indexes()` on startup; it's idempotent, so whichever starts first wins.

## Where it sits

```
devboard-work ────────┐
                      ├──> devboard:events ──> analytics-worker ──> Mongo (events)
devboard-integrations ┘                   └──> integrations (separate consumer group)
```

Analytics translates 17 of the 19 event types on the stream. It talks to nothing else —
no outbound HTTP, no other service depends on it yet.

## Running it

```
cd ..\devboard-infra
setup.bat        # brings up devboard-mongo along with the rest
redeploy.bat
```

There are no migrations. Indexes are created on startup in `ensure_indexes()`.

Standalone, with Mongo and Redis already up:

```
docker compose up --build
```

## Configuration

| var | notes |
|---|---|
| `MONGO_URI` | must include the database name — `get_default_database()` relies on it |
| `REDIS_URL` | must be `redis://devboard-redis:6379/0` in docker — compose does **not** override it, and `.env.example` still says `localhost` |
| `INTERNAL_API_KEY` | checked as `X-Service-Key` on `POST /events` |
| `JWT_SECRET` `JWT_ALGORITHM` | declared but not used yet — for report permissions |

## The event pipeline

```
XADD devboard:events           (work / integrations)
   │
   ▼
worker: xautoclaim + xreadgroup
   │
   ├─ action in IGNORED_ACTIONS? ──> ack and skip
   │
   ├─ translate_event(data) ──> ActivityEvent
   │     └─ ValidationError / ValueError / KeyError ──> failed_events, ack
   │
   ├─ id         = Redis message id
   ├─ created_at = timestamp parsed out of the message id
   │
   └─ insert into events, ack
```

### Translation

`app/consumer/translation.py` is the interesting file. It maps the wire vocabulary
published by other services onto this service's own action/metadata vocabulary. Two
consequences worth knowing:

- **The stored vocabulary is not the published one.** `ticket.status_changed` on the wire
  is stored as `action="ticket.updated"` with `metadata.field="status"`. All field changes
  share one action with a `field` tag, so the read side has one shape to handle instead of
  seven. The cost is that burndown queries filter on
  `action == "ticket.updated" AND metadata.field == "status" AND metadata.to == "Done"`
  rather than a bare action match. That's a deliberate consistency-over-directness call.
- **An unknown event raises `ValueError` and lands in `failed_events`.** That's on purpose:
  new event types have to be consciously admitted, not silently absorbed.

### Metadata shapes

`ActivityEvent.metadata` is a union, and a `model_validator` enforces that the shape
matches the action. Mongo would happily store anything; this is what stops "flexible"
becoming "unknowable". The reports layer can assume every row is exactly one of these:

| actions | metadata |
|---|---|
| `ticket.created` `ticket.deleted` `sprint.started` `sprint.completed` | `EmptyMetadata` |
| `ticket.updated` | `UpdatedMetadata` — `field`, `from`, `to` |
| `ticket.assigned` `ticket.unassigned` | `AssignmentMetadata` |
| `ticket.epic_linked` `ticket.epic_unlinked` | `EpicMetadata` |
| `label.applied` `label.removed` | `LabelMetadata` |
| `ticket.sprint_added` `ticket.sprint_removed` | `SprintAssignmentMetadata` |
| `ticket.commit_linked` | `CommitMetadata` |
| `comment.created` `comment.updated` `comment.deleted` | `CommentMetadata` |

`comment.mentioned` is in `IGNORED_ACTIONS` — integrations turns it into a notification,
but it isn't recorded as activity.

### Idempotency and replay

The Redis message id becomes Mongo's `_id`, and `insert_event` swallows `DuplicateKeyError`.
So redelivery is a no-op, and the consumer group is created with `id="0"` — meaning a fresh
group replays the entire stream and converges on the same collection. You can drop the
Mongo volume and rebuild the activity log from Redis.

`created_at` is derived from the millisecond prefix of the Redis message id, not from
ingestion time. Without that, replaying a backlog would stamp every historical event with
today's date and destroy the timeline.

## API

```
POST /events          X-Service-Key   ingest a single event
GET  /health
GET  /health/db
```

`POST /events` predates the Redis consumer — it was how Django core was originally going to
push events in. Nothing calls it now. It's kept for backfill and manual replay; if that
stops being useful it should be deleted rather than left open.

## Collections

- `events` — the activity log. `_id` is the Redis message id for consumer-ingested rows.
- `failed_events` — events that failed translation or validation, with the raw payload.

Indexes, all on `events`:

```
created_at ↓
(project_id ↑, created_at ↓)
(entity_type ↑, entity_id ↑)
(actor ↑, created_at ↓)
```

These are shaped for the reports that don't exist yet: a project timeline, per-entity
history, and per-person activity.

## Not built yet

**Reports.** `app/routers/reports.py`, `app/services/reports.py` and
`app/schemas/reports.py` are empty and the router is not registered. Velocity, burndown and
who-did-what are the reason this service exists and none of them are written.

The open design question is where the data for them comes from. Velocity needs a ticket's
story points *at the moment it was completed*, and the status event doesn't carry that —
so either reports replay the log to reconstruct it, the publisher enriches the event, or
analytics calls back into devboard-work. That choice should be made before the first
endpoint is written, because it decides whether this is a query problem or a wire-format
change across three repos.

Also outstanding:

- `app/exceptions.py` and `app/exception_handlers.py` are empty; there is no error layer.
- `get_recent_events` exists with no route.
- `JWT_SECRET` is loaded but nothing decodes a token — report permissions
  (contributor sees own activity, lead sees everyone's) are unimplemented.
- The consumer dead-letters schema errors immediately but retries infrastructure errors
  forever with no cap.
- `CONSUMER` is a hardcoded name, so only one worker replica is safe.
