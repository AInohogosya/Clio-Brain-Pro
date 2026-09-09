"""
Organization Control Service

Manages organizations, missions, roles, delegations, and decisions.
This is the core control plane for the AI organization.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import os

from .models import (
    Organization, Mission, Strategy, Workstream, Task, Episode, Action,
    MissionType, MissionStatus, TaskStatus, EpisodeStatus
)


class OrganizationStore:
    """In-memory store with JSON persistence for organizations and missions."""
    
    def __init__(self, data_dir: str = "./data"):
        self.data_dir = data_dir
        self.organizations: Dict[str, Organization] = {}
        self.missions: Dict[str, Mission] = {}
        self.strategies: Dict[str, Strategy] = {}
        self.workstreams: Dict[str, Workstream] = {}
        self.tasks: Dict[str, Task] = {}
        self.episodes: Dict[str, Episode] = {}
        self.actions: Dict[str, Action] = {}
        self._ensure_data_dir()
        self._load_state()
    
    def _ensure_data_dir(self):
        """Ensure data directory exists."""
        os.makedirs(self.data_dir, exist_ok=True)
    
    def _get_state_file(self, entity_type: str) -> str:
        """Get path to state file for entity type."""
        return os.path.join(self.data_dir, f"{entity_type}.json")
    
    def _save_state(self, entity_type: str, entities: Dict[str, Any]):
        """Save entities to JSON file."""
        filepath = self._get_state_file(entity_type)
        data = {
            k: self._serialize_entity(v) 
            for k, v in entities.items()
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def _load_state(self):
        """Load all entities from JSON files."""
        entity_types = {
            'organizations': Organization,
            'missions': Mission,
            'strategies': Strategy,
            'workstreams': Workstream,
            'tasks': Task,
            'episodes': Episode,
            'actions': Action
        }
        
        for entity_type, cls in entity_types.items():
            filepath = self._get_state_file(entity_type)
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    target_dict = getattr(self, entity_type)
                    for key, value in data.items():
                        target_dict[key] = self._deserialize_entity(value, cls)
    
    def _serialize_entity(self, entity: Any) -> Dict:
        """Serialize entity to dictionary."""
        if hasattr(entity, '__dict__'):
            data = entity.__dict__.copy()
            # Handle enums
            for k, v in data.items():
                if isinstance(v, Enum):
                    data[k] = v.value
                elif isinstance(v, datetime):
                    data[k] = v.isoformat()
            return data
        return entity
    
    def _deserialize_entity(self, data: Dict, cls: type) -> Any:
        """Deserialize dictionary to entity."""
        # Handle enum fields
        for field_name, field_value in data.items():
            if field_name == 'mission_type' and isinstance(field_value, str):
                data[field_name] = MissionType(field_value)
            elif field_name == 'status':
                # Determine which enum type based on class
                if cls == Mission:
                    data[field_name] = MissionStatus(field_value)
                elif cls == Task:
                    data[field_name] = TaskStatus(field_value)
                elif cls == Episode:
                    data[field_name] = EpisodeStatus(field_value)
            elif field_name in ('created_at', 'updated_at', 'started_at', 'ended_at', 'completed_at') and isinstance(field_value, str):
                data[field_name] = datetime.fromisoformat(field_value)
        
        # Create instance using dataclass fields
        instance = cls(**{k: v for k, v in data.items()})
        return instance
    
    def save_all(self):
        """Save all entities to disk."""
        self._save_state('organizations', self.organizations)
        self._save_state('missions', self.missions)
        self._save_state('strategies', self.strategies)
        self._save_state('workstreams', self.workstreams)
        self._save_state('tasks', self.tasks)
        self._save_state('episodes', self.episodes)
        self._save_state('actions', self.actions)


# Import Enum for type checking
from enum import Enum


class ControlService:
    """
    Main control service for managing the AI organization.
    
    Provides CRUD operations for all organizational entities
    and enforces the core philosophy that organizations and missions persist.
    """
    
    def __init__(self, store: Optional[OrganizationStore] = None):
        self.store = store or OrganizationStore()
    
    # Organization Management
    def create_organization(self, name: str, charter: str) -> Organization:
        """Create a new organization."""
        org = Organization(name=name, charter=charter)
        self.store.organizations[org.id] = org
        self.store.save_all()
        return org
    
    def get_organization(self, org_id: str) -> Optional[Organization]:
        """Get organization by ID."""
        return self.store.organizations.get(org_id)
    
    def list_organizations(self) -> List[Organization]:
        """List all organizations."""
        return list(self.store.organizations.values())
    
    def assign_role(self, org_id: str, role_name: str, description: str):
        """Assign a role within an organization."""
        org = self.get_organization(org_id)
        if org:
            org.assign_role(role_name, description)
            self.store.save_all()
    
    def allocate_budget(self, org_id: str, category: str, amount: float):
        """Allocate budget to a category."""
        org = self.get_organization(org_id)
        if org:
            org.allocate_budget(category, amount)
            self.store.save_all()
    
    # Mission Management
    def create_mission(
        self,
        organization_id: str,
        mission_type: MissionType,
        title: str,
        description: str,
        acceptance_criteria: Optional[List[str]] = None
    ) -> Mission:
        """Create a new mission."""
        mission = Mission(
            organization_id=organization_id,
            mission_type=mission_type,
            title=title,
            description=description,
            acceptance_criteria=acceptance_criteria or []
        )
        self.store.missions[mission.id] = mission
        self.store.save_all()
        return mission
    
    def get_mission(self, mission_id: str) -> Optional[Mission]:
        """Get mission by ID."""
        return self.store.missions.get(mission_id)
    
    def list_missions(self, organization_id: Optional[str] = None, status: Optional[MissionStatus] = None) -> List[Mission]:
        """List missions with optional filters."""
        missions = list(self.store.missions.values())
        if organization_id:
            missions = [m for m in missions if m.organization_id == organization_id]
        if status:
            missions = [m for m in missions if m.status == status]
        return missions
    
    def record_mission_attempt(
        self,
        mission_id: str,
        assumption: str,
        methodology: str,
        failure_cause: str
    ):
        """Record a failed attempt for a mission."""
        mission = self.get_mission(mission_id)
        if mission:
            mission.add_attempt_record(assumption, methodology, failure_cause)
            self.store.save_all()
    
    def pivot_mission_strategy(self, mission_id: str, new_approach: str):
        """Pivot to a new strategy for a mission."""
        mission = self.get_mission(mission_id)
        if mission:
            mission.pivot_strategy(new_approach)
            self.store.save_all()
    
    def satisfy_mission(self, mission_id: str):
        """Mark mission as satisfied."""
        mission = self.get_mission(mission_id)
        if mission:
            mission.satisfy()
            self.store.save_all()
    
    def cancel_mission(self, mission_id: str):
        """Cancel a mission (user-initiated)."""
        mission = self.get_mission(mission_id)
        if mission:
            mission.cancel()
            self.store.save_all()
    
    # Strategy Management
    def create_strategy(
        self,
        mission_id: str,
        name: str,
        description: str,
        workstreams: Optional[List[str]] = None
    ) -> Strategy:
        """Create a new strategy for a mission."""
        strategy = Strategy(
            mission_id=mission_id,
            name=name,
            description=description,
            workstreams=workstreams or []
        )
        self.store.strategies[strategy.id] = strategy
        self.store.save_all()
        return strategy
    
    def get_strategy(self, strategy_id: str) -> Optional[Strategy]:
        """Get strategy by ID."""
        return self.store.strategies.get(strategy_id)
    
    def list_strategies(self, mission_id: Optional[str] = None, active_only: bool = True) -> List[Strategy]:
        """List strategies with optional filters."""
        strategies = list(self.store.strategies.values())
        if mission_id:
            strategies = [s for s in strategies if s.mission_id == mission_id]
        if active_only:
            strategies = [s for s in strategies if s.is_active]
        return strategies
    
    # Task Management
    def create_task(
        self,
        mission_id: str,
        title: str,
        description: str,
        acceptance_criteria: Optional[List[str]] = None,
        workstream_id: Optional[str] = None
    ) -> Task:
        """Create a new task."""
        task = Task(
            mission_id=mission_id,
            workstream_id=workstream_id or "",
            title=title,
            description=description,
            acceptance_criteria=acceptance_criteria or []
        )
        self.store.tasks[task.id] = task
        self.store.save_all()
        return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        return self.store.tasks.get(task_id)
    
    def list_tasks(self, mission_id: Optional[str] = None, status: Optional[TaskStatus] = None) -> List[Task]:
        """List tasks with optional filters."""
        tasks = list(self.store.tasks.values())
        if mission_id:
            tasks = [t for t in tasks if t.mission_id == mission_id]
        if status:
            tasks = [t for t in tasks if t.status == status]
        return tasks
    
    def assign_task(self, task_id: str, agent_instance_id: str):
        """Assign a task to an agent instance."""
        task = self.get_task(task_id)
        if task:
            task.assigned_to = agent_instance_id
            task.status = TaskStatus.IN_PROGRESS
            self.store.save_all()
    
    def complete_task(self, task_id: str):
        """Mark task as completed."""
        task = self.get_task(task_id)
        if task:
            task.status = TaskStatus.COMPLETED
            self.store.save_all()
    
    def fail_task(self, task_id: str, reason: str):
        """Record task failure."""
        task = self.get_task(task_id)
        if task:
            task.record_failure(reason)
            self.store.save_all()
    
    # Episode Management
    def create_episode(self, task_id: str, agent_instance_id: str) -> Episode:
        """Create a new execution episode for a task."""
        episode = Episode(
            task_id=task_id,
            agent_instance_id=agent_instance_id
        )
        self.store.episodes[episode.id] = episode
        self.store.save_all()
        return episode
    
    def get_episode(self, episode_id: str) -> Optional[Episode]:
        """Get episode by ID."""
        return self.store.episodes.get(episode_id)
    
    def log_episode_action(self, episode_id: str, action_id: str):
        """Log an action in an episode."""
        episode = self.get_episode(episode_id)
        if episode:
            episode.add_action(action_id)
            self.store.save_all()
    
    def log_episode_message(self, episode_id: str, level: str, message: str, context: Optional[Dict] = None):
        """Add a log message to an episode."""
        episode = self.get_episode(episode_id)
        if episode:
            episode.add_log(level, message, context)
            self.store.save_all()
    
    def complete_episode(self, episode_id: str):
        """Mark episode as completed."""
        episode = self.get_episode(episode_id)
        if episode:
            episode.complete()
            self.store.save_all()
    
    def fail_episode(self, episode_id: str):
        """Mark episode as failed."""
        episode = self.get_episode(episode_id)
        if episode:
            episode.fail()
            self.store.save_all()
    
    # Action Management
    def create_action(
        self,
        episode_id: str,
        action_type: str,
        description: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Action:
        """Create a new action."""
        action = Action(
            episode_id=episode_id,
            action_type=action_type,
            description=description,
            parameters=parameters or {}
        )
        self.store.actions[action.id] = action
        self.store.save_all()
        return action
    
    def get_action(self, action_id: str) -> Optional[Action]:
        """Get action by ID."""
        return self.store.actions.get(action_id)
    
    def complete_action(self, action_id: str, result: Any = None, receipt: Optional[Dict] = None):
        """Mark action as completed."""
        action = self.get_action(action_id)
        if action:
            action.result = result
            if receipt:
                action.attach_receipt(receipt)
            else:
                action.status = "completed"
                action.completed_at = datetime.utcnow()
            self.store.save_all()
    
    def fail_action(self, action_id: str):
        """Mark action as failed."""
        action = self.get_action(action_id)
        if action:
            action.status = "failed"
            self.store.save_all()
    
    def mark_action_outcome_unknown(self, action_id: str):
        """Mark action outcome as unknown (needs reconciliation)."""
        action = self.get_action(action_id)
        if action:
            action.mark_outcome_unknown()
            self.store.save_all()
    
    # Query Methods
    def get_mission_status(self, mission_id: str) -> Dict[str, Any]:
        """Get comprehensive mission status including tasks and episodes."""
        mission = self.get_mission(mission_id)
        if not mission:
            return {"error": "Mission not found"}
        
        tasks = [t for t in self.store.tasks.values() if t.mission_id == mission_id]
        episodes = []
        for task in tasks:
            task_episodes = [e for e in self.store.episodes.values() if e.task_id == task.id]
            episodes.extend(task_episodes)
        
        return {
            "mission": mission,
            "tasks": tasks,
            "episodes": episodes,
            "active_tasks": len([t for t in tasks if t.status == TaskStatus.IN_PROGRESS]),
            "completed_tasks": len([t for t in tasks if t.status == TaskStatus.COMPLETED]),
            "failed_tasks": len([t for t in tasks if t.status == TaskStatus.FAILED])
        }
    
    def get_blocked_missions(self) -> List[Mission]:
        """Get all missions in blocked states."""
        blocked_statuses = [
            MissionStatus.RESOURCE_BLOCKED,
            MissionStatus.AUTHORITY_BLOCKED,
            MissionStatus.WAITING_EXTERNAL
        ]
        return [m for m in self.store.missions.values() if m.status in blocked_statuses]
    
    def get_monitoring_missions(self) -> List[Mission]:
        """Get all missions in monitoring state."""
        return [m for m in self.store.missions.values() if m.status == MissionStatus.MONITORING]
