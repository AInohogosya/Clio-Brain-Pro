"""
Reliability Service

Handles recovery, liveness auditing, backups, and generation management.
Detects stalled missions, orphaned workers, and unhandled events.
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import uuid
import json
import os
import shutil


@dataclass
class LivenessCheck:
    """Result of a liveness check."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    check_type: str = ""  # mission, worker, event
    entity_id: str = ""
    is_healthy: bool = True
    issues: List[str] = field(default_factory=list)
    checked_at: datetime = field(default_factory=datetime.utcnow)
    auto_remediated: bool = False


@dataclass
class BackupSnapshot:
    """Database backup snapshot."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    state_files: List[str] = field(default_factory=list)
    execution_generation: int = 0
    size_bytes: int = 0
    is_valid: bool = True
    restored_at: Optional[datetime] = None


class ReliabilityService:
    """
    Reliability service for liveness monitoring, recovery, and backups.
    """
    
    def __init__(self, data_dir: str = "./data", backup_dir: str = "./backups"):
        self.data_dir = data_dir
        self.backup_dir = backup_dir
        self.checks: Dict[str, LivenessCheck] = {}
        self.snapshots: Dict[str, BackupSnapshot] = {}
        self.current_generation: int = 1
        self._ensure_dirs()
        self._load_state()
    
    def _ensure_dirs(self):
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def _get_state_file(self) -> str:
        return os.path.join(self.data_dir, "reliability.json")
    
    def _save_state(self):
        filepath = self._get_state_file()
        data = {
            'checks': {k: self._serialize_check(v) for k, v in self.checks.items()},
            'snapshots': {k: self._serialize_snapshot(v) for k, v in self.snapshots.items()},
            'current_generation': self.current_generation
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def _load_state(self):
        filepath = self._get_state_file()
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                data = json.load(f)
                for key, value in data.get('checks', {}).items():
                    self.checks[key] = self._deserialize_check(value)
                for key, value in data.get('snapshots', {}).items():
                    self.snapshots[key] = self._deserialize_snapshot(value)
                self.current_generation = data.get('current_generation', 1)
    
    def _serialize_check(self, check: LivenessCheck) -> Dict:
        data = check.__dict__.copy()
        data['checked_at'] = check.checked_at.isoformat()
        return data
    
    def _deserialize_check(self, data: Dict) -> LivenessCheck:
        if 'checked_at' in data and isinstance(data['checked_at'], str):
            data['checked_at'] = datetime.fromisoformat(data['checked_at'])
        return LivenessCheck(**{k: v for k, v in data.items()})
    
    def _serialize_snapshot(self, snap: BackupSnapshot) -> Dict:
        data = snap.__dict__.copy()
        data['created_at'] = snap.created_at.isoformat()
        if snap.restored_at:
            data['restored_at'] = snap.restored_at.isoformat()
        return data
    
    def _deserialize_snapshot(self, data: Dict) -> BackupSnapshot:
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'restored_at' in data and data['restored_at']:
            data['restored_at'] = datetime.fromisoformat(data['restored_at'])
        return BackupSnapshot(**{k: v for k, v in data.items()})
    
    def check_mission_liveness(self, mission_id: str, 
                              last_activity: datetime,
                              status: str,
                              max_inactive_hours: int = 24) -> LivenessCheck:
        """Check if a mission is still alive."""
        now = datetime.utcnow()
        inactive_duration = now - last_activity
        
        check = LivenessCheck(
            check_type="mission",
            entity_id=mission_id
        )
        
        if status in ('satisfied', 'cancelled_by_user'):
            check.is_healthy = True  # Terminal states are fine
        elif inactive_duration > timedelta(hours=max_inactive_hours):
            check.is_healthy = False
            check.issues.append(f"Mission inactive for {inactive_duration}")
            
            if status == 'active':
                check.issues.append("Active mission appears stalled")
        
        self.checks[check.id] = check
        self._save_state()
        return check
    
    def check_worker_liveness(self, worker_id: str,
                             last_heartbeat: datetime,
                             lease_expiry: Optional[datetime] = None,
                             max_idle_minutes: int = 30) -> LivenessCheck:
        """Check if a worker is still alive."""
        now = datetime.utcnow()
        idle_duration = now - last_heartbeat
        
        check = LivenessCheck(
            check_type="worker",
            entity_id=worker_id
        )
        
        if idle_duration > timedelta(minutes=max_idle_minutes):
            check.is_healthy = False
            check.issues.append(f"Worker idle for {idle_duration}")
        
        if lease_expiry and now > lease_expiry:
            check.is_healthy = False
            check.issues.append("Worker lease has expired")
        
        self.checks[check.id] = check
        self._save_state()
        return check
    
    def detect_orphaned_workers(self, workers: Dict[str, Dict]) -> List[str]:
        """Detect workers with no valid lease."""
        orphaned = []
        now = datetime.utcnow()
        
        for worker_id, worker in workers.items():
            if worker.get('status') == 'busy':
                lease_id = worker.get('current_lease')
                if not lease_id:
                    orphaned.append(worker_id)
                else:
                    # Check if lease exists and is valid
                    lease = self.leases.get(lease_id) if hasattr(self, 'leases') else None
                    if not lease or not lease.is_valid():
                        orphaned.append(worker_id)
        
        return orphaned
    
    def detect_unhandled_events(self, events: List[Dict], 
                               max_age_hours: int = 1) -> List[Dict]:
        """Detect events that haven't been handled."""
        now = datetime.utcnow()
        unhandled = []
        
        for event in events:
            if event.get('status') != 'handled':
                event_time = datetime.fromisoformat(event.get('created_at', now.isoformat()))
                if now - event_time > timedelta(hours=max_age_hours):
                    unhandled.append(event)
        
        return unhandled
    
    def create_backup(self, state_files: List[str]) -> BackupSnapshot:
        """Create a backup snapshot of current state."""
        snapshot_id = str(uuid.uuid4())
        snapshot_dir = os.path.join(self.backup_dir, snapshot_id)
        os.makedirs(snapshot_dir, exist_ok=True)
        
        copied_files = []
        total_size = 0
        
        for filepath in state_files:
            if os.path.exists(filepath):
                dest = os.path.join(snapshot_dir, os.path.basename(filepath))
                shutil.copy2(filepath, dest)
                copied_files.append(dest)
                total_size += os.path.getsize(dest)
        
        snapshot = BackupSnapshot(
            state_files=copied_files,
            execution_generation=self.current_generation,
            size_bytes=total_size
        )
        
        self.snapshots[snapshot.id] = snapshot
        self._save_state()
        return snapshot
    
    def restore_backup(self, snapshot_id: str) -> bool:
        """Restore from a backup snapshot."""
        snapshot = self.snapshots.get(snapshot_id)
        if not snapshot or not snapshot.is_valid:
            return False
        
        # Advance generation to revoke stale credentials
        self.current_generation += 1
        
        # Restore files
        for filepath in snapshot.state_files:
            if os.path.exists(filepath):
                # Copy back to data directory
                dest = os.path.join(self.data_dir, os.path.basename(filepath))
                shutil.copy2(filepath, dest)
        
        snapshot.restored_at = datetime.utcnow()
        self._save_state()
        
        return True
    
    def get_latest_snapshot(self) -> Optional[BackupSnapshot]:
        """Get the most recent backup snapshot."""
        if not self.snapshots:
            return None
        return max(self.snapshots.values(), key=lambda s: s.created_at)
    
    def cleanup_old_backups(self, keep_count: int = 5):
        """Remove old backups, keeping only the most recent ones."""
        if len(self.snapshots) <= keep_count:
            return
        
        # Sort by creation time
        sorted_snapshots = sorted(
            self.snapshots.values(),
            key=lambda s: s.created_at,
            reverse=True
        )
        
        # Remove old ones
        for snapshot in sorted_snapshots[keep_count:]:
            # Delete snapshot directory
            for filepath in snapshot.state_files:
                if os.path.exists(filepath):
                    os.remove(filepath)
            
            del self.snapshots[snapshot.id]
        
        self._save_state()
    
    def record_recovery_action(self, entity_type: str, entity_id: str,
                              action: str, success: bool):
        """Record a recovery action taken."""
        check_id = f"{entity_type}_{entity_id}_{uuid.uuid4().hex[:8]}"
        check = LivenessCheck(
            check_type=f"recovery_{entity_type}",
            entity_id=entity_id,
            is_healthy=success,
            issues=[action],
            auto_remediated=success
        )
        self.checks[check_id] = check
        self._save_state()
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get overall system health summary."""
        total_checks = len(self.checks)
        healthy_checks = len([c for c in self.checks.values() if c.is_healthy])
        
        recent_checks = [
            c for c in self.checks.values()
            if datetime.utcnow() - c.checked_at < timedelta(hours=1)
        ]
        
        return {
            'total_checks': total_checks,
            'healthy_checks': healthy_checks,
            'unhealthy_checks': total_checks - healthy_checks,
            'recent_checks': len(recent_checks),
            'current_generation': self.current_generation,
            'total_backups': len(self.snapshots),
            'latest_backup': self.get_latest_snapshot().__dict__ if self.get_latest_snapshot() else None
        }
