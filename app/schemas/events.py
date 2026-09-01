from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EmptyMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

class UpdatedMetadata(BaseModel):
    field: Literal["status", "priority", "type", "due_date", "title", "description", "story_points"]
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None

class AssignmentMetadata(BaseModel):
    assignee_id: UUID
    assignee_email: str | None = None

class EpicMetadata(BaseModel):
    epic_id: UUID
    epic_key: str | None = None

class LabelMetadata(BaseModel):
    label_id: UUID
    label_name: str | None = None

class SprintAssignmentMetadata(BaseModel):
    sprint_id: UUID
    sprint_name: str | None = None

class CommitMetadata(BaseModel):
    commit_sha: str
    commit_url: str
    commit_message: str
    repo: str

class CommentMetadata(BaseModel):
    ticket_id: UUID

UPDATE_ACTIONS = {"ticket.updated"} 
ASSIGNMENT_ACTIONS = {"ticket.assigned", "ticket.unassigned"}
EPIC_ACTIONS = {"ticket.epic_linked", "ticket.epic_unlinked"}
LABEL_ACTIONS = {"label.applied", "label.removed"}
SPRINT_ASSIGNMENT_ACTIONS ={"ticket.sprint_added", "ticket.sprint_removed"}
SPRINT_ACTIONS = {"sprint.started", "sprint.completed"}
COMMIT_ACTIONS = {"ticket.commit_linked"}
COMMENT_ACTIONS = {"comment.created", "comment.updated", "comment.deleted"}

IGNORED_ACTIONS = {"comment.mentioned"}

def expected_entity_type_for(action: str) -> str:
    if action in SPRINT_ACTIONS:
        return "sprint"
    if action in COMMENT_ACTIONS:
        return "comment"
    return "ticket"
class ActivityEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str | None = Field(default=None, alias="_id")
    actor: UUID
    actor_email: str | None = None
    action: str
    entity_type: Literal['ticket', 'comment', 'sprint', 'project']
    entity_id: UUID
    entity_key: str
    project_id: UUID
    metadata: EmptyMetadata | UpdatedMetadata | AssignmentMetadata | EpicMetadata | LabelMetadata | SprintAssignmentMetadata | CommitMetadata | CommentMetadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def check_metadata_matches_action(self):
        expected_type = (
            UpdatedMetadata if self.action in UPDATE_ACTIONS else
            AssignmentMetadata if self.action in ASSIGNMENT_ACTIONS else
            EpicMetadata if self.action in EPIC_ACTIONS else
            LabelMetadata if self.action in LABEL_ACTIONS else
            SprintAssignmentMetadata if self.action in SPRINT_ASSIGNMENT_ACTIONS else
            CommitMetadata if self.action in COMMIT_ACTIONS else
            CommentMetadata if self.action in COMMENT_ACTIONS else
            EmptyMetadata
        )
        if not isinstance(self.metadata, expected_type):
            raise ValueError(f"'{self.action}' requires {expected_type.__name__} metadata")  # noqa: TRY004
        expected_entity_type = expected_entity_type_for(self.action)
        if self.entity_type != expected_entity_type:
            raise ValueError(f"'{self.action}' requires entity_type='{expected_entity_type}', got '{self.entity_type}'")
        return self

