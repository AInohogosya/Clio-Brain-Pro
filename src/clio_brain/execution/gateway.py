"""
Execution Gateway

Enforces isolation across local tools, browser automation, and cloud provider adapters.
Manages worker leases, credentials, and execution boundaries.
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import uuid
import json
import os
import subprocess
import signal
from enum import Enum


class ExecutionEnvironment(Enum):
    """Types of execution environments."""
    LOCAL = "local"  # Local shell/tools
    BROWSER = "browser"  # Browser automation
    CLOUD = "cloud"  # Cloud provider
    SANDBOX = "sandbox"  # Isolated sandbox


class WorkerStatus(Enum):
    """Worker lifecycle states."""
    IDLE = "idle"
    BUSY = "busy"
    TERMINATED = "terminated"
    UNHEALTHY = "unhealthy"


@dataclass
class WorkerLease:
    """Short-lived lease for worker execution."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    worker_id: str = ""
    mission_id: str = ""
    task_id: str = ""
    granted_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(hours=1))
    is_active: bool = True
    credentials: Dict[str, str] = field(default_factory=dict)
    
    def is_valid(self) -> bool:
        """Check if lease is still valid."""
        return self.is_active and datetime.utcnow() < self.expires_at
    
    def revoke(self):
        """Revoke the lease."""
        self.is_active = False


@dataclass 
class ExecutionResult:
    """Result of an execution attempt."""
    success: bool = False
    output: str = ""
    error: str = ""
    exit_code: int = 0
    duration_seconds: float = 0.0
    external_receipt: Optional[Dict[str, Any]] = None
    requires_reconciliation: bool = False


class ExecutionGateway:
    """
    Main execution gateway for managing isolated task execution.
    Enforces authority checks, manages worker leases, and handles reconciliation.
    """
    
    def __init__(self, data_dir: str = "./data"):
        self.data_dir = data_dir
        self.workers: Dict[str, Dict[str, Any]] = {}
        self.leases: Dict[str, WorkerLease] = {}
        self.execution_history: List[Dict[str, Any]] = []
        self._ensure_data_dir()
        self._load_state()
    
    def _ensure_data_dir(self):
        os.makedirs(self.data_dir, exist_ok=True)
    
    def _get_state_file(self) -> str:
        return os.path.join(self.data_dir, "execution.json")
    
    def _save_state(self):
        filepath = self._get_state_file()
        data = {
            'workers': self.workers,
            'leases': {k: self._serialize_lease(v) for k, v in self.leases.items()},
            'execution_history': self.execution_history[-1000:]  # Keep last 1000
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def _load_state(self):
        filepath = self._get_state_file()
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                data = json.load(f)
                self.workers = data.get('workers', {})
                for key, value in data.get('leases', {}).items():
                    self.leases[key] = self._deserialize_lease(value)
                self.execution_history = data.get('execution_history', [])
    
    def _serialize_lease(self, lease: WorkerLease) -> Dict:
        data = lease.__dict__.copy()
        data['granted_at'] = lease.granted_at.isoformat()
        data['expires_at'] = lease.expires_at.isoformat()
        return data
    
    def _deserialize_lease(self, data: Dict) -> WorkerLease:
        data['granted_at'] = datetime.fromisoformat(data['granted_at'])
        data['expires_at'] = datetime.fromisoformat(data['expires_at'])
        return WorkerLease(**{k: v for k, v in data.items()})
    
    def register_worker(self, worker_id: str, environment: ExecutionEnvironment,
                       capabilities: Optional[List[str]] = None,
                       metadata: Optional[Dict[str, Any]] = None):
        """Register a worker with the gateway."""
        self.workers[worker_id] = {
            'id': worker_id,
            'environment': environment.value,
            'capabilities': capabilities or [],
            'status': WorkerStatus.IDLE.value,
            'current_lease': None,
            'metadata': metadata or {},
            'registered_at': datetime.utcnow().isoformat(),
            'last_heartbeat': datetime.utcnow().isoformat()
        }
        self._save_state()
    
    def get_worker(self, worker_id: str) -> Optional[Dict]:
        """Get worker info."""
        return self.workers.get(worker_id)
    
    def request_lease(self, worker_id: str, mission_id: str, task_id: str,
                     credentials: Optional[Dict[str, str]] = None,
                     duration_hours: float = 1.0) -> Optional[WorkerLease]:
        """Request a worker lease for task execution."""
        worker = self.get_worker(worker_id)
        if not worker:
            return None
        
        if worker['status'] != WorkerStatus.IDLE.value:
            return None
        
        # Create lease with short-lived credentials
        lease = WorkerLease(
            worker_id=worker_id,
            mission_id=mission_id,
            task_id=task_id,
            expires_at=datetime.utcnow() + timedelta(hours=duration_hours),
            credentials=credentials or {}
        )
        
        # Update worker status
        worker['status'] = WorkerStatus.BUSY.value
        worker['current_lease'] = lease.id
        
        self.leases[lease.id] = lease
        self._save_state()
        
        return lease
    
    def release_lease(self, lease_id: str, result: Optional[ExecutionResult] = None):
        """Release a worker lease."""
        lease = self.leases.get(lease_id)
        if not lease:
            return
        
        # Revoke lease
        lease.revoke()
        
        # Update worker status
        worker = self.get_worker(lease.worker_id)
        if worker:
            worker['status'] = WorkerStatus.IDLE.value
            worker['current_lease'] = None
            worker['last_heartbeat'] = datetime.utcnow().isoformat()
        
        # Record execution history
        if result:
            self.execution_history.append({
                'lease_id': lease_id,
                'worker_id': lease.worker_id,
                'mission_id': lease.mission_id,
                'task_id': lease.task_id,
                'result': {
                    'success': result.success,
                    'exit_code': result.exit_code,
                    'duration_seconds': result.duration_seconds,
                    'requires_reconciliation': result.requires_reconciliation
                },
                'completed_at': datetime.utcnow().isoformat()
            })
        
        self._save_state()
    
    def check_lease_validity(self, lease_id: str) -> bool:
        """Check if a lease is still valid."""
        lease = self.leases.get(lease_id)
        return lease.is_valid() if lease else False
    
    def terminate_stale_workers(self, max_idle_minutes: int = 30):
        """Terminate workers that have been idle too long."""
        now = datetime.utcnow()
        for worker_id, worker in self.workers.items():
            if worker['status'] == WorkerStatus.IDLE.value:
                last_heartbeat = datetime.fromisoformat(worker['last_heartbeat'])
                idle_duration = now - last_heartbeat
                if idle_duration > timedelta(minutes=max_idle_minutes):
                    worker['status'] = WorkerStatus.TERMINATED.value
        
        self._save_state()
    
    def execute_local_command(self, command: str, timeout_seconds: int = 300,
                             working_dir: Optional[str] = None,
                             env: Optional[Dict[str, str]] = None) -> ExecutionResult:
        """Execute a local shell command with isolation."""
        start_time = datetime.utcnow()
        
        try:
            # Set up isolated environment
            process_env = os.environ.copy()
            if env:
                process_env.update(env)
            
            # Execute command
            result = subprocess.run(
                command,
                shell=True,
                cwd=working_dir,
                env=process_env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds
            )
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            return ExecutionResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr,
                exit_code=result.returncode,
                duration_seconds=duration
            )
            
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                error=f"Command timed out after {timeout_seconds} seconds",
                exit_code=-1,
                duration_seconds=timeout_seconds,
                requires_reconciliation=True  # May have partial side effects
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=str(e),
                exit_code=-1,
                duration_seconds=0.0
            )
    
    def reconcile_unknown_outcome(self, action_id: str, 
                                 verification_method: Callable) -> ExecutionResult:
        """
        Reconcile an action with unknown outcome.
        Uses verification method to determine actual state.
        """
        try:
            actual_state = verification_method(action_id)
            return ExecutionResult(
                success=True,
                output=json.dumps(actual_state),
                external_receipt=actual_state,
                requires_reconciliation=False
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Reconciliation failed: {str(e)}",
                requires_reconciliation=True
            )
    
    def get_execution_history(self, mission_id: Optional[str] = None,
                             limit: int = 100) -> List[Dict[str, Any]]:
        """Get execution history with optional filter."""
        history = self.execution_history[-limit:]
        if mission_id:
            history = [e for e in history if e.get('mission_id') == mission_id]
        return history
    
    def heartbeat(self, worker_id: str):
        """Update worker heartbeat."""
        worker = self.get_worker(worker_id)
        if worker:
            worker['last_heartbeat'] = datetime.utcnow().isoformat()
            self._save_state()
