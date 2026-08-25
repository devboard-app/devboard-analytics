from uuid import UUID

from app.schemas.events import (
    ActivityEvent,
    AssignmentMetadata,
    EmptyMetadata,
    EpicMetadata,
    LabelMetadata,
    SprintAssignmentMetadata,
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
    
    if event_type == "ticket.updated":
        return ActivityEvent(
            actor=UUID(data["actor_id"]),
            action="ticket.updated",
            entity_type="ticket",
            entity_id=UUID(data["ticket_id"]),
            entity_key=data["ticket_key"],
            project_id=UUID(data["project_id"]),
            metadata=UpdatedMetadata.model_validate({"field": data["field"], "from": data["from_value"], "to": data["to_value"]}),
        )

    if event_type == "ticket.deleted":
        return ActivityEvent(
            actor=UUID(data["actor_id"]),
            action="ticket.deleted",
            entity_type="ticket",
            entity_id=UUID(data["ticket_id"]),
            entity_key=data["ticket_key"],
            project_id=UUID(data["project_id"]),
            metadata=EmptyMetadata(),
        )

    if event_type == "ticket.unassigned":
        return ActivityEvent(
            actor=UUID(data["actor_id"]),
            action="ticket.unassigned",
            entity_type="ticket",
            entity_id=UUID(data["ticket_id"]),
            entity_key=data["ticket_key"],
            project_id=UUID(data["project_id"]),
            metadata=AssignmentMetadata(assignee_id=UUID(data["previous_assignee_id"])),
        )

    if event_type in ("ticket.epic_linked", "ticket.epic_unlinked"):
        return ActivityEvent(
            actor=UUID(data["actor_id"]),
            action=event_type,
            entity_type="ticket",
            entity_id=UUID(data["ticket_id"]),
            entity_key=data["ticket_key"],
            project_id=UUID(data["project_id"]),
            metadata=EpicMetadata(epic_id=UUID(data["epic_id"]), epic_key=data.get("epic_key")),
        )

    if event_type in ("label.applied", "label.removed"):
        return ActivityEvent(
            actor=UUID(data["actor_id"]),
            action=event_type,
            entity_type="ticket",
            entity_id=UUID(data["ticket_id"]),
            entity_key=data["ticket_key"],
            project_id=UUID(data["project_id"]),
            metadata=LabelMetadata(label_id=UUID(data["label_id"]), label_name=data.get("label_name")),
        )

    if event_type in ("ticket.sprint_added", "ticket.sprint_removed"):
        return ActivityEvent(
            actor=UUID(data["actor_id"]),
            action=event_type,
            entity_type="ticket",
            entity_id=UUID(data["ticket_id"]),
            entity_key=data["ticket_key"],
            project_id=UUID(data["project_id"]),
            metadata=SprintAssignmentMetadata(sprint_id=UUID(data["sprint_id"]), sprint_name=data.get("sprint_name")),
        )
    raise ValueError(f"No translation defined for event '{event_type}'")