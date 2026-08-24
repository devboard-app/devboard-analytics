from uuid import UUID

from app.schemas.events import (
    ActivityEvent,
    AssignmentMetadata,
    EmptyMetadata,
    UpdatedMetadata,
)


def translate_event(data: dict) -> ActivityEvent:
    event_type = data["event"]

    if event_type == "ticket.created":
        return ActivityEvent(
            actor=UUID(data["actor_id"]),
            action="ticket.created",
            entity_type="ticket",
            entity_id=UUID(data["ticket_id"]),
            entity_key=data["ticket_key"],
            project_id=UUID(data["project_id"]),
            metadata=EmptyMetadata(),
        )

    if event_type == "ticket.assigned":
        return ActivityEvent(
            actor=UUID(data["actor_id"]),
            action="ticket.assigned",
            entity_type="ticket",
            entity_id=UUID(data["ticket_id"]),
            entity_key=data["ticket_key"],
            project_id=UUID(data["project_id"]),
            metadata=AssignmentMetadata(assignee_id=UUID(data["recipient_id"])),
        )

    if event_type == "ticket.status_changed":
        return ActivityEvent(
            actor=UUID(data["actor_id"]),
            action="ticket.updated",
            entity_type="ticket",
            entity_id=UUID(data["ticket_id"]),
            entity_key=data["ticket_key"],
            project_id=UUID(data["project_id"]),
            metadata=UpdatedMetadata.model_validate({"field": "status", "from": data["from_status"], "to": data["to_status"]}),
        )

    if event_type in ("sprint.started", "sprint.completed"):
        return ActivityEvent(
            actor=UUID(data["actor_id"]),
            action=event_type,
            entity_type="sprint",
            entity_id=UUID(data["sprint_id"]),
            entity_key=data["sprint_name"],
            project_id=UUID(data["project_id"]), 
            metadata=EmptyMetadata(),
        )

    raise ValueError(f"No translation defined for event '{event_type}'")