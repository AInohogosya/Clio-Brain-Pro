"""
Planning & Scheduling Service

Handles mission reviews, portfolio scoring, strategy selection, and task dispatching.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import uuid
import json
import os


@dataclass
class PortfolioCandidate:
    """A candidate mission or task for portfolio scoring."""
    id: str = ""
    candidate_type: str = ""  # mission, task
    title: str = ""
    description: str = ""
    
    # Scoring factors
    expected_value: float = 0.0  # V: Expected user value
    information_gain: float = 0.0  # I: Information gain
    urgency: float = 0.0  # D: Urgency/deadline pressure
    aging_penalty: float = 0.0  # A: Aging/wait penalty
    blocked_benefit: float = 0.0  # B: Benefit to blocked missions
    resource_cost: float = 0.0  # C: Resource cost
    downside_risk: float = 0.0  # R: Downside risk
    
    # Weights (configurable)
    weight_value: float = 1.0
    weight_info: float = 0.5
    weight_urgency: float = 0.8
    weight_aging: float = 0.3
    weight_blocked: float = 0.6
    weight_cost: float = 0.4
    weight_risk: float = 0.5
    
    @property
    def score(self) -> float:
        """
        Calculate portfolio score using weighted formula:
        S = w_v*V + w_i*I + w_d*D + w_a*A + w_b*B - w_c*C - w_r*R
        """
        return (
            self.weight_value * self.expected_value +
            self.weight_info * self.information_gain +
            self.weight_urgency * self.urgency +
            self.weight_aging * self.aging_penalty +
            self.weight_blocked * self.blocked_benefit -
            self.weight_cost * self.resource_cost -
            self.weight_risk * self.downside_risk
        )


@dataclass
class MissionReview:
    """Periodic review of a mission's progress."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    mission_id: str = ""
    reviewed_at: datetime = field(default_factory=datetime.utcnow)
    reviewer: str = ""  # Agent ID or "system"
    
    # Assessment
    is_on_track: bool = True
    current_strategy_effective: bool = True
    obstacles: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    # Actions
    requires_replan: bool = False
    requires_resources: bool = False
    requires_authority: bool = False
    should_enter_monitoring: bool = False
    
    notes: str = ""


class PlanningService:
    """
    Planning service for portfolio management and task scheduling.
    """
    
    def __init__(self, data_dir: str = "./data"):
        self.data_dir = data_dir
        self.candidates: Dict[str, PortfolioCandidate] = {}
        self.reviews: Dict[str, MissionReview] = {}
        self.scheduled_tasks: List[Dict[str, Any]] = []
        self._ensure_data_dir()
        self._load_state()
    
    def _ensure_data_dir(self):
        os.makedirs(self.data_dir, exist_ok=True)
    
    def _get_state_file(self) -> str:
        return os.path.join(self.data_dir, "planning.json")
    
    def _save_state(self):
        filepath = self._get_state_file()
        data = {
            'candidates': {k: self._serialize_candidate(v) for k, v in self.candidates.items()},
            'reviews': {k: self._serialize_review(v) for k, v in self.reviews.items()},
            'scheduled_tasks': self.scheduled_tasks
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def _load_state(self):
        filepath = self._get_state_file()
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                data = json.load(f)
                for key, value in data.get('candidates', {}).items():
                    self.candidates[key] = self._deserialize_candidate(value)
                for key, value in data.get('reviews', {}).items():
                    self.reviews[key] = self._deserialize_review(value)
                self.scheduled_tasks = data.get('scheduled_tasks', [])
    
    def _serialize_candidate(self, c: PortfolioCandidate) -> Dict:
        return c.__dict__.copy()
    
    def _deserialize_candidate(self, data: Dict) -> PortfolioCandidate:
        return PortfolioCandidate(**{k: v for k, v in data.items()})
    
    def _serialize_review(self, r: MissionReview) -> Dict:
        data = r.__dict__.copy()
        data['reviewed_at'] = r.reviewed_at.isoformat()
        return data
    
    def _deserialize_review(self, data: Dict) -> MissionReview:
        if 'reviewed_at' in data and isinstance(data['reviewed_at'], str):
            data['reviewed_at'] = datetime.fromisoformat(data['reviewed_at'])
        return MissionReview(**{k: v for k, v in data.items()})
    
    def add_candidate(self, candidate: PortfolioCandidate):
        """Add a candidate to the portfolio."""
        self.candidates[candidate.id] = candidate
        self._save_state()
    
    def remove_candidate(self, candidate_id: str):
        """Remove a candidate from the portfolio."""
        if candidate_id in self.candidates:
            del self.candidates[candidate_id]
            self._save_state()
    
    def update_candidate_scores(self, candidate_id: str, **kwargs):
        """Update scoring factors for a candidate."""
        candidate = self.candidates.get(candidate_id)
        if candidate:
            for key, value in kwargs.items():
                if hasattr(candidate, key):
                    setattr(candidate, key, value)
            self._save_state()
    
    def get_prioritized_candidates(self, min_score: float = 0.0) -> List[PortfolioCandidate]:
        """Get candidates sorted by score (highest first)."""
        candidates = [c for c in self.candidates.values() if c.score >= min_score]
        return sorted(candidates, key=lambda c: c.score, reverse=True)
    
    def select_next_task(self) -> Optional[PortfolioCandidate]:
        """Select the highest-priority candidate for execution."""
        prioritized = self.get_prioritized_candidates()
        return prioritized[0] if prioritized else None
    
    def schedule_task(self, candidate_id: str, agent_id: Optional[str] = None, 
                     scheduled_for: Optional[datetime] = None):
        """Schedule a task for execution."""
        candidate = self.candidates.get(candidate_id)
        if not candidate:
            return
        
        self.scheduled_tasks.append({
            'candidate_id': candidate_id,
            'agent_id': agent_id,
            'scheduled_for': scheduled_for.isoformat() if scheduled_for else None,
            'status': 'scheduled',
            'created_at': datetime.utcnow().isoformat()
        })
        self._save_state()
    
    def create_mission_review(
        self,
        mission_id: str,
        reviewer: str,
        is_on_track: bool = True,
        current_strategy_effective: bool = True,
        obstacles: Optional[List[str]] = None,
        recommendations: Optional[List[str]] = None,
        requires_replan: bool = False,
        requires_resources: bool = False,
        requires_authority: bool = False,
        should_enter_monitoring: bool = False,
        notes: str = ""
    ) -> MissionReview:
        """Create a mission review."""
        review = MissionReview(
            mission_id=mission_id,
            reviewer=reviewer,
            is_on_track=is_on_track,
            current_strategy_effective=current_strategy_effective,
            obstacles=obstacles or [],
            recommendations=recommendations or [],
            requires_replan=requires_replan,
            requires_resources=requires_resources,
            requires_authority=requires_authority,
            should_enter_monitoring=should_enter_monitoring,
            notes=notes
        )
        self.reviews[review.id] = review
        self._save_state()
        return review
    
    def get_mission_reviews(self, mission_id: str) -> List[MissionReview]:
        """Get all reviews for a mission."""
        return [r for r in self.reviews.values() if r.mission_id == mission_id]
    
    def get_latest_review(self, mission_id: str) -> Optional[MissionReview]:
        """Get the most recent review for a mission."""
        reviews = self.get_mission_reviews(mission_id)
        if not reviews:
            return None
        return max(reviews, key=lambda r: r.reviewed_at)
    
    def classify_obstacle(self, obstacle_description: str) -> str:
        """
        Classify an obstacle into categories:
        - transient_failure
        - knowledge_gap
        - tooling_deficit
        - resource_constraint
        - contradictory_requirement
        - scientific_uncertainty
        """
        obstacle_lower = obstacle_description.lower()
        
        if any(word in obstacle_lower for word in ['timeout', 'retry', 'temporary', 'network']):
            return 'transient_failure'
        elif any(word in obstacle_lower for word in ['unknown', 'learn', 'understand', 'research']):
            return 'knowledge_gap'
        elif any(word in obstacle_lower for word in ['tool', 'api', 'library', 'missing']):
            return 'tooling_deficit'
        elif any(word in obstacle_lower for word in ['budget', 'quota', 'limit', 'resource']):
            return 'resource_constraint'
        elif any(word in obstacle_lower for word in ['conflict', 'contradict', 'impossible']):
            return 'contradictory_requirement'
        elif any(word in obstacle_lower for word in ['hypothesis', 'experiment', 'uncertain']):
            return 'scientific_uncertainty'
        
        return 'knowledge_gap'  # Default
    
    def recommend_pivot(self, mission_id: str, failed_approach: str, 
                       attempt_history: List[Dict]) -> str:
        """
        Recommend a strategic pivot based on failure history.
        """
        if not attempt_history:
            return "Try a different decomposition of the problem"
        
        # Analyze failure patterns
        failure_causes = [a.get('failure_cause', '').lower() for a in attempt_history]
        
        # Check for repeated failures
        if len(attempt_history) >= 2:
            if 'knowledge' in ' '.join(failure_causes):
                return "Seek additional information or expert consultation before proceeding"
            elif 'tool' in ' '.join(failure_causes):
                return "Build or acquire necessary tooling before attempting again"
            elif 'resource' in ' '.join(failure_causes):
                return "Secure additional resources or reduce scope"
        
        return "Modify approach: try alternative methodology or break into smaller tasks"
    
    def should_enter_monitoring(self, mission_id: str, 
                               active_tasks: int = 0,
                               blocked_tasks: int = 0) -> bool:
        """
        Determine if a mission should enter monitoring state.
        """
        # No worthwhile immediate actions
        if active_tasks == 0 and blocked_tasks > 0:
            return True
        
        # Check recent reviews
        latest_review = self.get_latest_review(mission_id)
        if latest_review and latest_review.should_enter_monitoring:
            return True
        
        return False
