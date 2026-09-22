# devboard-analytics

**What happened, and how are we doing?** It keeps a log of everything that happens in DevBoard. It builds reports from that log: activity, velocity, burndown and cycle time.

- **Port:** `8006`
- **Stack:** FastAPI, MongoDB (Motor), Redis Streams
- **Two containers, one image:**

| Container | Command | Job |
|---|---|---|
| `devboard-analytics` | `uvicorn app.main:app` | HTTP API (the reports). |
| `devboard-analytics-worker` | `python -m app.consumer.worker` | Reads the event stream and fills MongoDB. |

---

## Start here (about 5 minutes)

1. Open a terminal in `devboard-infra`.
2. Run `setup.bat`. It starts MongoDB, creates the analytics user and starts both containers.
3. Open `http://localhost:8006/health`. You should see `{"status": "ok"}`.
4. Want fake data to try the reports? See "Demo data" below.

Only want this service? MongoDB and Redis must already be running. Then:

```bash
docker compose up --build
```

There are no migrations. Indexes are created when the service starts.

---

## What it does

1. **Listens** to the `devboard:events` Redis stream.
2. **Translates** each event into one clean `ActivityEvent` and saves it in MongoDB.
3. **Serves reports** built from the saved events.

Every service that publishes to the stream ends up here. This is DevBoard's record of "what happened".

---

## How it fits

```
devboard-work ────────┐
                      ├──> devboard:events ──> analytics-worker ──> MongoDB (events)
devboard-integrations ┘                   └──> integrations (its own reader)

Browser ──JWT──> analytics API ──> devboard-work  (what is my role in this project?)
                              └──> MongoDB
```

Analytics has no user data. For every report request it asks devboard-work for the caller's project role.

---

## Reports

Base path: `/reports`. All need `Authorization: Bearer <jwt>`.

| Method | Path | Who can call | What you get |
|---|---|---|---|
| `GET` | `/reports/projects/{project_id}/activity/` | Project members | Activity feed. Uses `limit` (max 100) and `offset`. Leads can add `actor=<user_id>`. |
| `GET` | `/reports/projects/{project_id}/activity/summary/` | Project members | Who did what. |
| `GET` | `/reports/projects/{project_id}/velocity/` | Project **leads** | Points planned and points finished, per sprint. Plus the average. |
| `GET` | `/reports/projects/{project_id}/cycle-time/` | Project **leads** | How long tickets take. Median lead time and cycle time. |
| `GET` | `/reports/sprints/{sprint_id}/burndown/` | Project **leads** | Work left per day, next to the ideal line. |

**Contributors see only their own activity.** Leads see everyone's.

**Velocity, cycle-time and burndown are cached** in Redis per project (burndown per sprint), so a report is instant as long as nothing changed in that project since it was last computed. The cache is invalidated the moment a new event is recorded for that project — not on a timer, so it's never stale.

Terms:

- **Lead time:** from ticket created to done.
- **Cycle time:** time the ticket was actually being worked on.
- **Velocity:** story points finished in a sprint.

Other routes:

| Method | Path | What it does |
|---|---|---|
| `POST` | `/events/` | Save one event by hand. Needs `X-Service-Key`. Kept for backfill. Nothing calls it today. |
| `GET` | `/health` | Is the service up? |
| `GET` | `/health/db` | Can it reach MongoDB? |

Errors: `401` no or bad token. `403` not allowed. `404` sprint not found. `409` sprint has no start or end date. `503` devboard-work is down.

---

## How events get saved

```
Redis stream ──> worker
                  ├─ event is ignored? ──> ack and skip
                  ├─ translate it ──> ActivityEvent
                  │     └─ bad event? ──> failed_events, ack
                  ├─ id         = the outbox row id if the publisher sent one, else the Redis message id
                  ├─ created_at = time inside the Redis message id
                  └─ insert into events, ack
```

Why it is safe:

1. **Same event twice is fine.** The id is the MongoDB `_id`. A second insert is ignored — this holds even if the publisher redelivers the same logical event with a new Redis message id, as long as it sends the same outbox id.
2. **You can rebuild everything.** A new consumer group reads the stream from the start. Delete the Mongo volume, restart, and the log comes back from Redis.
3. **Times stay true.** `created_at` comes from the Redis id, not from "now". Rebuilding does not change history.
4. **Failures are capped, but a MongoDB outage doesn't burn through them.** The worker checks MongoDB is reachable before processing anything; while it's down, it waits instead of reading or retrying messages, so a healthy message doesn't get pushed into `failed_events` just because Mongo happened to be briefly unreachable. A message still fails after 3 genuine attempts.
5. **Stuck messages are retried.** Messages pending for 30 seconds are picked up again, up to 5000 at a time — matched to how many `xautoclaim` can actually reclaim in one pass, so a long pending list doesn't leave messages past the first 100 with an untracked retry count.

### Names are translated

The stored name is not always the published name. Example: `ticket.status_changed` is saved as `ticket.updated` with `metadata.field = "status"`. Every field change has one shape, so reports are simpler.

`app/consumer/translation.py` does this. An **unknown event fails** and goes to `failed_events`. New event types must be added on purpose.

`comment.mentioned` is ignored. It is a notification, not activity.

### What is saved per event

Each event has a fixed metadata shape. It is checked when saved.

| Actions | Metadata |
|---|---|
| `ticket.created` | Story points and status |
| `ticket.deleted` | Empty |
| `sprint.started`, `sprint.completed` | Start date and end date |
| `ticket.updated` | `field`, `from`, `to` |
| `ticket.assigned`, `ticket.unassigned` | Assignment |
| `ticket.epic_linked`, `ticket.epic_unlinked` | Epic |
| `label.applied`, `label.removed` | Label |
| `ticket.sprint_added`, `ticket.sprint_removed` | Sprint |
| `ticket.commit_linked` | Commit |
| `comment.created`, `comment.updated`, `comment.deleted` | Comment |

---

## MongoDB

Database: `activity_db`.

| Collection | What is in it |
|---|---|
| `events` | The activity log. |
| `failed_events` | Events that could not be saved, with the raw data. |

Indexes on `events`:

- `created_at` (newest first)
- `project_id` + `created_at`
- `entity_type` + `entity_id`
- `actor` + `created_at`

---

## Settings

Copy `.env.example` to `.env`.

| Variable | What it is |
|---|---|
| `MONGO_URI` | Must include the database name (`.../activity_db`). |
| `REDIS_URL` | In Docker use `redis://devboard-redis:6379/0`. Compose does **not** override it, and `.env.example` may still say `localhost`. |
| `JWT_SECRET` | Same value as devboard-auth. Checks the caller's token. |
| `INTERNAL_API_KEY` | Checked as `X-Service-Key` on `POST /events/`. Also sent to devboard-work. |
| `DEVBOARD_WORK_URL` | Where devboard-work lives. Used for role checks. |

`devboard-infra\setup.bat` also reads `ANALYTICS_DB_PASSWORD` from this `.env` to create the MongoDB user.

---

## Demo data

The stack must be up. Run from this folder:

1. `.venv\Scripts\python.exe scripts\bootstrap_demo.py` – creates users, a team and a project. Writes `scripts\demo_ids.json`.
2. `.venv\Scripts\python.exe scripts\seed_events.py --wipe` – adds a two-sprint story to MongoDB. Set `MONGO_URI` first (see the top of the script). `--wipe` deletes existing events.

Tests:

```bash
pytest
```

---

## Not done yet

- **No route for `get_recent_events`.** The function exists, nothing calls it.
