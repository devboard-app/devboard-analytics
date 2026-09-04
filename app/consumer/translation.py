from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from app.schemas.events import (
    ActivityEvent,
    AssignmentMetadata,
    CommentMetadata,
    CommitMetadata,
    EmptyMetadata,
    EpicMetadata,
    LabelMetadata,
    SprintAssignmentMetadata,
    UpdatedMetadata,
)


def _build_event(data: dict, action: str, entity_type: Literal['ticket', 'comment', 'sprint', 'project'], entity_id: str, entity_key: str, metadata) -> ActivityEvent:
    return ActivityEvent(
        actor=UUID(data["actor_id"]),
        action=action,
        entity_type=entity_type,
        entity_id=UUID(entity_id),
        entity_key=entity_key,
        project_id=UUID(data["project_id"]),
        metadata=metadata,
    )

def translate_event(data: dict) -> ActivityEvent:
    event_type = data["event"]

    if event_type == "ticket.created":
        return _build_event(data, "ticket.created", "ticket", data["ticket_id"], data["ticket_key"], EmptyMetadata())

    if event_type == "ticket.assigned":
        return _build_event(data, "ticket.assigned", "ticket", data["ticket_id"], data["ticket_key"], AssignmentMetadata(assignee_id=UUID(data["recipient_id"])))

    if event_type == "ticket.status_changed":
        return _build_event(data, "ticket.updated", "ticket", data["ticket_id"], data["ticket_key"], UpdatedMetadata.model_validate({"field": "status", "from": data.get("from_status"), "to": data.get("to_status")}))

    if event_type in ("sprint.started", "sprint.completed"):
        return _build_event(data, event_type, "sprint", data["sprint_id"], data["sprint_name"], EmptyMetadata())

    if event_type == "ticket.updated":
        return _build_event(data, "ticket.updated", "ticket", data["ticket_id"], data["ticket_key"], UpdatedMetadata.model_validate({"field": data["field"], "from": data.get("from_value"), "to": data.get("to_value")}))

    if event_type == "ticket.deleted":
        return _build_event(data, "ticket.deleted", "ticket", data["ticket_id"], data["ticket_key"], EmptyMetadata())

    if event_type == "ticket.unassigned":
        return _build_event(data, "ticket.unassigned", "ticket", data["ticket_id"], data["ticket_key"], AssignmentMetadata(assignee_id=UUID(data["previous_assignee_id"])))

    if event_type in ("ticket.epic_linked", "ticket.epic_unlinked"):
        return _build_event(data, event_type, "ticket", data["ticket_id"], data["ticket_key"], EpicMetadata(epic_id=UUID(data["epic_id"]), epic_key=data.get("epic_key")))

    if event_type in ("label.applied", "label.removed"):
        return _build_event(data, event_type, "ticket", data["ticket_id"], data["ticket_key"], LabelMetadata(label_id=UUID(data["label_id"]), label_name=data.get("label_name")))

    if event_type in ("ticket.sprint_added", "ticket.sprint_removed"):
        return _build_event(data, event_type, "ticket", data["ticket_id"], data["ticket_key"], SprintAssignmentMetadata(sprint_id=UUID(data["sprint_id"]), sprint_name=data.get("sprint_name")))

    if event_type == "ticket.commit_linked":
        return _build_event(data, "ticket.commit_linked", "ticket", data["ticket_id"], data["ticket_key"], CommitMetadata( commit_sha=data["commit_sha"], commit_url=data["commit_url"], commit_message=data["commit_message"], repo=data["repo"]),)

    if event_type in ("comment.created", "comment.updated", "comment.deleted"):
        return _build_event(data, event_type, "comment", data["comment_id"], data["ticket_key"], CommentMetadata(ticket_id=UUID(data["ticket_id"])))

    raise ValueError(f"No translation defined for event '{event_type}'")

def created_at_from_message_id(message_id: str) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(str(message_id).split("-")[0]) / 1000, timezone.utc)
    except ValueError:
        return None