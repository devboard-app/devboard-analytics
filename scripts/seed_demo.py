"""Seed a full demo workspace: verified users, two teams, three projects with
labels, epics, sprints, tickets on every board column, and comments with
@mentions.

Talks to the live stack over HTTP (auth, core, work), exactly as the frontend
does. Two shortcuts, both dev-only, because the email-verification link can't be
clicked by a script:

  1. `is_verified` is flipped straight in auth_db.
  2. The user is synced to core (`/api/users/sync/`) with the internal service
     key -- the step auth's verify-email endpoint normally does.

Idempotent: users, teams and memberships are reused. A project that already
exists is left untouched (its tickets are not seeded twice).

Usage (stack must be up):

    .venv/Scripts/python.exe scripts/seed_demo.py

It also runs automatically as the one-shot `seed-demo` job in
devboard-infra/stack.yml. There the service URLs point at the container names
and DATABASE_URL_SYNC (from devboard-auth/.env) is used to reach auth_db
directly, since `docker exec` isn't available inside a container.

INTERNAL_API_KEY is read from the environment, or from ../devboard-core/.env.
Every account uses the password below.
"""
import os
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import httpx

AUTH_URL = os.environ.get("SEED_AUTH_URL", "http://localhost:18001")
CORE_URL = os.environ.get("SEED_CORE_URL", "http://localhost:18003")
WORK_URL = os.environ.get("SEED_WORK_URL", "http://localhost:18004")
# Set inside the stack; unset on the host, where `docker exec devboard-db` is used.
AUTH_DB_URL = os.environ.get("DATABASE_URL_SYNC")

PASSWORD = "demopassword"  # noqa: S105  (dev-only)
# example.com is reserved: nothing is delivered there, and auth's email
# validator accepts it (unlike .test / .local). Core derives the username from
# the part before the @, so these become @olivia, @adam, ...
EMAIL_DOMAIN = "example.com"
USERS = ["olivia", "adam", "maria", "dan", "vera", "sam"]

TEAMS = [
    {
        "name": "Acme Engineering",
        "description": "Main product team.",
        "owner": "olivia",
        "members": {"adam": "admin", "maria": "member", "dan": "member", "vera": "viewer", "sam": "member"},
        "projects": [
            # Created by `lead`, who becomes project lead automatically.
            {"key": "WEB", "name": "DevBoard Web", "lead": "olivia",
             "contributors": ["adam", "maria", "dan"], "content": "web"},
            {"key": "MOB", "name": "Mobile App", "lead": "adam",
             "contributors": ["maria", "sam"], "content": "mobile"},
        ],
    },
    {
        "name": "Side Quests",
        "description": "Small experiments outside the main roadmap.",
        "owner": "maria",
        "members": {"dan": "admin", "olivia": "member", "vera": "viewer"},
        "projects": [
            {"key": "LAND", "name": "Landing Page", "lead": "maria",
             "contributors": ["dan", "olivia"], "content": "landing"},
        ],
    },
]

# Where a ticket ends up: "backlog", or (sprint index, status).
BACKLOG = "backlog"

CONTENT = {
    "web": {
        "labels": [("frontend", "#6366F1"), ("backend", "#10B981"), ("ux", "#F59E0B"), ("urgent", "#EF4444")],
        "epics": ["Authentication revamp", "Board experience"],
        "sprints": [
            {"name": "Sprint 1", "goal": "Ship login and the first board", "start": -28, "days": 14, "state": "completed"},
            {"name": "Sprint 2", "goal": "Polish the board and notifications", "start": -7, "days": 14, "state": "active"},
            {"name": "Sprint 3", "goal": "Reports and chat", "start": 7, "days": 14, "state": "created"},
        ],
        "tickets": [
            # title, type, priority, points, assignee, epic, labels, where
            ("Login page with email + password", "feature", "high", 5, "maria", 0, ["frontend"], (0, "done")),
            ("JWT refresh on 401", "task", "high", 3, "adam", 0, ["backend"], (0, "done")),
            ("Verify-email screen", "feature", "medium", 2, "maria", 0, ["frontend", "ux"], (0, "done")),
            ("Kanban board columns", "feature", "high", 8, "dan", 1, ["frontend"], (0, "done")),
            ("Drag and drop between columns", "feature", "high", 5, "dan", 1, ["frontend", "ux"], (1, "in_progress")),
            ("Ticket drawer closes on outside click", "improvement", "medium", 2, "maria", 1, ["ux"], (1, "in_review")),
            ("Notifications drawer", "feature", "medium", 5, "adam", None, ["frontend"], (1, "in_progress")),
            ("Board crashes when a sprint has no tickets", "bug", "critical", 3, "olivia", 1, ["urgent", "frontend"], (1, "done")),
            ("Mention autocomplete in comments", "feature", "medium", 3, "maria", None, ["frontend", "ux"], (1, "todo")),
            ("Password reset email template", "task", "low", 1, "adam", 0, ["backend"], (1, "done")),
            ("Avatar upload to MinIO", "feature", "medium", 5, "dan", None, ["backend", "frontend"], (1, "todo")),
            ("Velocity chart", "feature", "medium", 5, "dan", None, ["frontend"], (2, "todo")),
            ("Project chat assistant", "feature", "low", 8, "adam", None, ["backend"], (2, "todo")),
            ("Dark mode toggle icon is clipped", "bug", "low", 1, None, None, ["ux"], BACKLOG),
            ("Keyboard shortcuts", "improvement", "low", 3, None, 1, ["ux"], BACKLOG),
            ("Rate-limit login attempts", "task", "high", 3, "adam", 0, ["backend"], BACKLOG),
        ],
        # ticket index, author, body. {name} is replaced with that user's @username.
        "comments": [
            (4, "dan", "Dragging works, but the drop target flickers. Looking into dragleave now."),
            (4, "olivia", "{maria} can you pair with {dan} on this? You did the drawer."),
            (4, "maria", "Sure, after standup."),
            (5, "maria", "Ready for review. Esc and outside click both close it."),
            (5, "olivia", "Looks good. {adam} please double-check the notifications drawer uses the same hook."),
            (7, "olivia", "Hotfix merged. **Root cause:** empty sprint returned `null` columns."),
            (6, "adam", "Backend events are in. Frontend polling every 30s for now."),
        ],
    },
    "mobile": {
        "labels": [("ios", "#0EA5E9"), ("android", "#22C55E"), ("design", "#EC4899")],
        "epics": ["Offline mode"],
        "sprints": [
            {"name": "Mobile Sprint 1", "goal": "App shell and login", "start": -3, "days": 14, "state": "active"},
        ],
        "tickets": [
            ("App shell with bottom tabs", "feature", "high", 5, "maria", None, ["design"], (0, "in_progress")),
            ("Login screen", "feature", "high", 3, "sam", None, ["ios", "android"], (0, "todo")),
            ("Push notification permissions", "task", "medium", 2, "sam", None, ["ios"], (0, "in_review")),
            ("Cache tickets locally", "feature", "medium", 8, None, 0, ["ios", "android"], BACKLOG),
            ("Sync queue for offline edits", "feature", "medium", 8, None, 0, [], BACKLOG),
            ("Splash screen stretches on tablets", "bug", "low", 1, "maria", None, ["android", "design"], BACKLOG),
        ],
        "comments": [
            (0, "maria", "Tabs: Board, Backlog, Notifications, Profile. {adam} OK?"),
            (0, "adam", "Yes. Keep Reports web-only for now."),
            (2, "sam", "iOS done, Android needs a runtime prompt too."),
        ],
    },
    "landing": {
        "labels": [("copy", "#A855F7"), ("seo", "#14B8A6")],
        "epics": [],
        "sprints": [
            {"name": "Launch week", "goal": "Get the page live", "start": -2, "days": 7, "state": "active"},
        ],
        "tickets": [
            ("Hero section copy", "task", "high", 2, "olivia", None, ["copy"], (0, "in_progress")),
            ("Pricing table", "feature", "medium", 3, "dan", None, [], (0, "todo")),
            ("Meta tags and Open Graph image", "task", "medium", 1, "dan", None, ["seo"], (0, "done")),
            ("Blog section", "feature", "low", 5, None, None, ["seo", "copy"], BACKLOG),
        ],
        "comments": [
            (0, "maria", "{olivia} first draft by Friday?"),
            (0, "olivia", "Yes, sharing it in the ticket."),
        ],
    },
}


def internal_api_key() -> str:
    key = os.environ.get("INTERNAL_API_KEY")
    if key:
        return key
    env_file = Path(__file__).resolve().parents[2] / "devboard-core" / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("INTERNAL_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"')
    sys.exit("INTERNAL_API_KEY not set and not found in devboard-core/.env")


def call(client: httpx.Client, method: str, url: str, headers: dict | None = None,
         json: dict | None = None, ok: tuple[int, ...] = (200, 201)) -> httpx.Response:
    r = client.request(method, url, headers=headers, json=json)
    if r.status_code not in ok:
        sys.exit(f"{method} {url} -> {r.status_code} {r.text[:300]}")
    return r


# --- users -------------------------------------------------------------------

def register(client: httpx.Client, email: str) -> None:
    r = client.post(f"{AUTH_URL}/auth/register/", json={"email": email, "password": PASSWORD})
    if r.status_code == 201:
        print(f"  registered {email}")
    elif r.status_code == 409:
        print(f"  {email} already exists")
    elif r.status_code == 429:
        sys.exit("register is rate-limited (10/hour per IP). Wait, or flush the "
                 "register:* keys in Redis, then re-run.")
    else:
        # The verification email is sent after the user is committed, so a mail
        # failure still leaves a usable user. Verification below makes it usable.
        print(f"  {email} -> {r.status_code} (user is created anyway, continuing)")


def wait_until_up(client: httpx.Client, urls: list[str], timeout: int = 300) -> None:
    """The services start alongside this job; any answer below 500 means up."""
    deadline = time.monotonic() + timeout
    for url in urls:
        while True:
            try:
                if client.get(url).status_code < 500:
                    break
            except httpx.TransportError:
                pass
            if time.monotonic() > deadline:
                sys.exit(f"{url} did not come up within {timeout}s")
            time.sleep(3)


def auth_db(sql: str) -> list[list[str]]:
    """Run SQL against auth_db (dev only) and return the rows as lists of strings."""
    if AUTH_DB_URL:
        import psycopg2  # only in the stack job, which runs on the auth image

        # SQLAlchemy's "postgresql+psycopg2://" isn't a URL psycopg2 knows.
        with psycopg2.connect(AUTH_DB_URL.replace("+psycopg2", "", 1)) as conn, conn.cursor() as cur:
            cur.execute(sql)
            return [[str(v) for v in row] for row in cur.fetchall()] if cur.description else []
    result = subprocess.run(
        ["docker", "exec", "devboard-db", "sh", "-c",
         f'psql -U "$POSTGRES_USER" -d auth_db -t -A -F "|" -c "{sql}"'],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        sys.exit(f"auth_db query failed:\n{result.stderr.strip()}")
    return [line.split("|") for line in result.stdout.splitlines() if "|" in line or line.strip()]


def existing_emails(emails: list[str]) -> set[str]:
    """Registration is rate-limited per IP, so re-runs skip users that already exist."""
    quoted = ", ".join(f"'{e}'" for e in emails)
    return {row[0] for row in auth_db(f"SELECT email FROM users WHERE email IN ({quoted});")}


def verify_and_sync(client: httpx.Client, emails: list[str], service_key: str) -> None:
    """Do what clicking the verification link does: mark verified + create the core profile."""
    quoted = ", ".join(f"'{e}'" for e in emails)
    rows = [r for r in auth_db(
        f"UPDATE users SET is_verified = true WHERE email IN ({quoted}) RETURNING id, email, role;"
    ) if len(r) == 3]
    if len(rows) != len(emails):
        sys.exit(f"expected {len(emails)} users in auth_db, found {len(rows)}")
    for user_id, email, role in rows:
        call(client, "POST", f"{CORE_URL}/api/users/sync/",
             headers={"X-Service-Key": service_key},
             json={"user_id": user_id, "email": email, "role": role})
    print(f"  verified + synced {len(rows)} users")


def login(client: httpx.Client, email: str) -> dict:
    r = call(client, "POST", f"{AUTH_URL}/auth/login/", json={"email": email, "password": PASSWORD})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = call(client, "GET", f"{CORE_URL}/api/users/me/", headers=headers).json()
    return {"email": email, "user_id": me["user_id"], "username": me["username"], "headers": headers}


# --- teams / projects ----------------------------------------------------------

def find_or_create_team(client: httpx.Client, owner: dict, spec: dict) -> str:
    teams = call(client, "GET", f"{WORK_URL}/api/teams/?limit=100", headers=owner["headers"]).json()["results"]
    for team in teams:
        if team["name"] == spec["name"]:
            print(f"  team '{spec['name']}' exists")
            return team["id"]
    team = call(client, "POST", f"{WORK_URL}/api/teams/", headers=owner["headers"],
                json={"name": spec["name"], "description": spec["description"]}).json()
    print(f"  created team '{spec['name']}'")
    return team["id"]


def find_or_create_project(client: httpx.Client, lead: dict, team_id: str, spec: dict) -> tuple[str, bool]:
    base = f"{WORK_URL}/api/teams/{team_id}/projects/"
    for project in call(client, "GET", f"{base}?limit=100", headers=lead["headers"]).json()["results"]:
        if project["key"] == spec["key"]:
            print(f"  project {spec['key']} exists, not seeding its content again")
            return project["id"], False
    project = call(client, "POST", base, headers=lead["headers"],
                   json={"name": spec["name"], "key": spec["key"]}).json()
    print(f"  created project {spec['key']}")
    return project["id"], True


# --- project content -----------------------------------------------------------

def seed_content(client: httpx.Client, users: dict, lead: dict, team_id: str, project_id: str, content: dict) -> None:
    base = f"{WORK_URL}/api/teams/{team_id}/projects/{project_id}"
    h = lead["headers"]

    labels = {}
    for name, color in content["labels"]:
        labels[name] = call(client, "POST", f"{base}/labels/", headers=h, json={"name": name, "color": color}).json()["id"]

    epics = [call(client, "POST", f"{base}/tickets/", headers=h,
                  json={"title": title, "type": "epic", "priority": "medium"}).json()["id"]
             for title in content["epics"]]

    today = date.today()
    sprints = []
    for s in content["sprints"]:
        start = today + timedelta(days=s["start"])
        sprint = call(client, "POST", f"{base}/sprints/", headers=h, json={
            "name": s["name"], "goal": s["goal"],
            "start_date": start.isoformat(), "end_date": (start + timedelta(days=s["days"])).isoformat(),
        }).json()
        sprints.append({**s, "id": sprint["id"], "tickets": []})

    tickets = []
    for title, type_, priority, points, assignee, epic, label_names, where in content["tickets"]:
        body = {"title": title, "type": type_, "priority": priority, "story_points": points,
                "description": f"Demo ticket: {title.lower()}."}
        if assignee:
            body["assignee_id"] = users[assignee]["user_id"]
        if epic is not None:
            body["parent_epic"] = epics[epic]
        ticket_id = call(client, "POST", f"{base}/tickets/", headers=h, json=body).json()["id"]
        for name in label_names:
            call(client, "POST", f"{base}/tickets/{ticket_id}/labels/", headers=h, json={"label_id": labels[name]})
        tickets.append(ticket_id)
        if where != BACKLOG:
            sprint_index, status = where
            sprints[sprint_index]["tickets"].append((ticket_id, status))

    # Sprints run in list order, so a completed one is closed before the next starts
    # (only one active sprint per project). Adding a ticket moves it Backlog -> Todo.
    for sprint in sprints:
        for ticket_id, _ in sprint["tickets"]:
            call(client, "POST", f"{base}/sprints/{sprint['id']}/tickets/", headers=h, json={"ticket_id": ticket_id})
        if sprint["state"] == "created":
            continue
        call(client, "POST", f"{base}/sprints/{sprint['id']}/start/", headers=h)
        for ticket_id, status in sprint["tickets"]:
            if status != "todo":
                call(client, "PATCH", f"{base}/tickets/{ticket_id}/", headers=h, json={"status": status})
        if sprint["state"] == "completed":
            call(client, "POST", f"{base}/sprints/{sprint['id']}/complete/", headers=h)

    mentions = {name: f"@{u['username']}" for name, u in users.items()}
    for index, author, text in content["comments"]:
        call(client, "POST", f"{base}/tickets/{tickets[index]}/comments/", headers=users[author]["headers"],
             json={"body": text.format(**mentions)})

    print(f"    {len(labels)} labels, {len(epics)} epics, {len(tickets)} tickets, "
          f"{len(sprints)} sprints, {len(content['comments'])} comments")


def main() -> None:
    service_key = internal_api_key()
    emails = {name: f"{name}@{EMAIL_DOMAIN}" for name in USERS}

    with httpx.Client(timeout=30) as client:
        wait_until_up(client, [f"{AUTH_URL}/health", f"{CORE_URL}/api/users/me/", f"{WORK_URL}/api/teams/"])
        print("users")
        existing = existing_emails(list(emails.values()))
        for email in emails.values():
            if email in existing:
                print(f"  {email} already exists")
            else:
                register(client, email)
        verify_and_sync(client, list(emails.values()), service_key)
        users = {name: login(client, email) for name, email in emails.items()}

        for team_spec in TEAMS:
            print(f"\nteam {team_spec['name']}")
            owner = users[team_spec["owner"]]
            team_id = find_or_create_team(client, owner, team_spec)
            for name, role in team_spec["members"].items():
                call(client, "POST", f"{WORK_URL}/api/teams/{team_id}/members/", headers=owner["headers"],
                     json={"email": users[name]["email"], "role": role}, ok=(201, 409))

            for project_spec in team_spec["projects"]:
                lead = users[project_spec["lead"]]
                project_id, created = find_or_create_project(client, lead, team_id, project_spec)
                for name in project_spec["contributors"]:
                    call(client, "POST", f"{WORK_URL}/api/teams/{team_id}/projects/{project_id}/members/",
                         headers=lead["headers"], json={"user_id": users[name]["user_id"], "role": "contributor"},
                         ok=(201, 409))
                if created:
                    seed_content(client, users, lead, team_id, project_id, CONTENT[project_spec["content"]])

    print(f"\ndone. Log in with any of these (password: {PASSWORD}):")
    for team_spec in TEAMS:
        roles = {team_spec["owner"]: "owner", **team_spec["members"]}
        print(f"  {team_spec['name']}: " + ", ".join(f"{emails[n]} ({r})" for n, r in roles.items()))


if __name__ == "__main__":
    main()
