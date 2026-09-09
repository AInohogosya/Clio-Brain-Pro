"""
Core data models for Clio Brain organizational structure.

Separates intent (Organization, Mission, Strategy) from execution (Task, Episode, Action).
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid


class MissionType(Enum):
    """Types of missions the organization can pursue."""
    OUTCOME = "outcome"  # Build and deliver a specific application
    STANDING = "standing"  # Operate and maintain SLA/SLO
    RESEARCH = "research"  # Investigate open questions
    OPPORTUNITY = "opportunity"  # Identify business opportunities
    CAPABILITY = "capability"  # Improve organizational capabilities


class MissionStatus(Enum):
    """Mission lifecycle states."""
    ACTIVE = "active"
    REPLANNING = "replanning"
    WAITING_EXTERNAL = "waiting_external"
    RESOURCE_BLOCKED = "resource_blocked"
    AUTHORITY_BLOCKED = "authority_blocked"
    MONITORING = "monitoring"
    SATISFIED = "satisfied"
    CANCELLED_BY_USER = "cancelled_by_user"


class TaskStatus(Enum):
    """Task execution states."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


class EpisodeStatus(Enum):
    """Episode execution states."""
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"


@dataclass
class Organization:
    """
    The top-level organizational unit.
    Holds charter, roles, assets, budgets, and decision rights.
    Organizations persist across all missions and strategies.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    charter: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    roles: Dict[str, str] = field(default_factory=dict)  # role_name -> description
    assets: Dict[str, Any] = field(default_factory=dict)
    budgets: Dict[str, float] = field(default_factory=dict)
    decision_rights: Dict[str, List[str]] = field(default_factory=dict)
    
    def assign_role(self, role_name: str, description: str):
        """Assign a role within the organization."""
        self.roles[role_name] = description
    
    def allocate_budget(self, category: str, amount: float):
        """Allocate budget to a category."""
        self.budgets[category] = self.budgets.get(category, 0.0) + amount


@dataclass
class Mission:
    """
    A persistent objective that outlives individual strategies and tasks.
    Missions do not automatically fail - they transition to blocked/monitoring states.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: str = ""
    mission_type: MissionType = MissionType.OUTCOME
    title: str = ""
    description: str = ""
    acceptance_criteria: List[str] = field(default_factory=list)
    status: MissionStatus = MissionStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    strategy_history: List[str] = field(default_factory=list)
    attempt_history: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_attempt_record(self, assumption: str, methodology: str, failure_cause: str):
        """Record a failed attempt for learning and pivot."""
        self.attempt_history.append({
            "assumption": assumption,
            "methodology": methodology,
            "failure_cause": failure_cause,
            "recorded_at": datetime.utcnow().isoformat()
        })
        self.updated_at = datetime.utcnow()
    
    def pivot_strategy(self, new_approach: str):
        """Record a strategic pivot."""
        self.strategy_history.append(new_approach)
        self.status = MissionStatus.REPLANNING
        self.updated_at = datetime.utcnow()
    
    def satisfy(self):
        """Mark mission as satisfied."""
        self.status = MissionStatus.SATISFIED
        self.updated_at = datetime.utcnow()
    
    def cancel(self):
        """Cancel mission (user-initiated only)."""
        self.status = MissionStatus.CANCELLED_BY_USER
        self.updated_at = datetime.utcnow()


@dataclass
class Strategy:
    """
    A specific approach to advancing a mission.
    Strategies are replaceable when they fail.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    mission_id: str = ""
    name: str = ""
    description: str = ""
    workstreams: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True


@dataclass
class Workstream:
    """
    A coherent coordination area within a strategy.
    Groups related tasks for better organization.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategy_id: str = ""
    name: str = ""
    description: str = ""
    tasks: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)


@dataclass
class Task:
    """
    A bounded deliverable with acceptance criteria.
    Tasks can fail without failing the mission.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workstream_id: str = ""
    mission_id: str = ""
    title: str = ""
    description: str = ""
    acceptance_criteria: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: Optional[str] = None  # Agent instance ID
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    attempts: int = 0
    max_attempts: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return self.attempts < self.max_attempts
    
    def record_failure(self, reason: str):
        """Record a task failure."""
        self.attempts += 1
        self.status = TaskStatus.FAILED
        self.metadata["last_failure_reason"] = reason
        self.updated_at = datetime.utcnow()


@dataclass
class Episode:
    """
    A bounded execution session for a task.
    Episodes are short-lived and tied to specific agent instances.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    agent_instance_id: str = ""
    status: EpisodeStatus = EpisodeStatus.RUNNING
    started_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    actions: List[str] = field(default_factory=list)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_action(self, action_id: str):
        """Record an action taken in this episode."""
        self.actions.append(action_id)
    
    def add_log(self, level: str, message: str, context: Optional[Dict] = None):
        """Add a log entry."""
        self.logs.append({
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            "context": context or {}
        })
    
    def complete(self):
        """Mark episode as completed."""
        self.status = EpisodeStatus.COMPLETED
        self.ended_at = datetime.utcnow()
    
    def fail(self):
        """Mark episode as failed."""
        self.status = EpisodeStatus.FAILED
        self.ended_at = datetime.utcnow()


@dataclass
class Action:
    """
    A concrete operation performed by an agent.
    Actions may have external side effects that need reconciliation.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    episode_id: str = ""
    action_type: str = ""
    description: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending, running, completed, failed, outcome_unknown
    result: Optional[Any] = None
    external_receipt: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    requires_reconciliation: bool = False
    
    def mark_outcome_unknown(self):
        """Mark action as having unknown outcome (needs reconciliation)."""
        self.status = "outcome_unknown"
        self.requires_reconciliation = True
    
    def attach_receipt(self, receipt: Dict[str, Any]):
        """Attach external receipt for verification."""
        self.external_receipt = receipt
        self.status = "completed"
        self.completed_at = datetime.utcnow()
