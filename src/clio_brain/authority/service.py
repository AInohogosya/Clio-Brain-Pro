"""
Authority Service

Manages standing grants, credential vault, and revocations.
Ensures every proposed operation falls within valid standing grants.
"""

from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
import uuid
import json
import os
from enum import Enum


class GrantType(Enum):
    """Types of authority grants."""
    DEVELOPMENT = "development"  # Code development, repository creation
    RESEARCH = "research"  # Information gathering, analysis
    DEPLOYMENT = "deployment"  # Cloud resource provisioning
    MARKETING = "marketing"  # Truthful marketing campaigns
    FINANCIAL = "financial"  # Financial operations (limited)
    LEGAL = "legal"  # Requires human participation


class AuthorityLevel(Enum):
    """Authority levels for operations."""
    AUTONOMOUS = "autonomous"  # Can execute without approval
    NOTIFIED = "notified"  # Execute but notify humans
    APPROVAL_REQUIRED = "approval_required"  # Requires explicit approval
    HUMAN_ONLY = "human_only"  # Cannot be executed by AI


@dataclass
class StandingGrant:
    """
    A standing grant of authority for autonomous operations.
    Grants are scoped by type, resource limits, and conditions.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: str = ""
    grant_type: GrantType = GrantType.DEVELOPMENT
    name: str = ""
    description: str = ""
    authority_level: AuthorityLevel = AuthorityLevel.AUTONOMOUS
    resource_limits: Dict[str, float] = field(default_factory=dict)  # e.g., {"compute_hours": 100, "usd": 500}
    allowed_operations: List[str] = field(default_factory=list)
    denied_operations: List[str] = field(default_factory=list)
    conditions: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    
    def check_resource_limit(self, resource_type: str, amount: float) -> bool:
        """Check if operation is within resource limits."""
        limit = self.resource_limits.get(resource_type, float('inf'))
        return amount <= limit
    
    def is_operation_allowed(self, operation: str) -> bool:
        """Check if specific operation is allowed."""
        if operation in self.denied_operations:
            return False
        if not self.allowed_operations:  # Empty means all allowed except denied
            return True
        return operation in self.allowed_operations
    
    def revoke(self):
        """Revoke this grant."""
        self.is_active = False
        self.revoked_at = datetime.utcnow()


@dataclass
class Credential:
    """
    Stored credential for external services.
    Credentials are encrypted at rest and accessed via grants.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: str = ""
    grant_id: str = ""
    service_name: str = ""
    credential_type: str = ""  # api_key, oauth, ssh_key, etc.
    encrypted_data: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_valid: bool = True
    
    def mark_used(self):
        """Mark credential as used."""
        self.last_used_at = datetime.utcnow()
    
    def invalidate(self):
        """Invalidate this credential."""
        self.is_valid = False


@dataclass
class AuthorityRequest:
    """
    Request for authority to perform an operation.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: str = ""
    operation: str = ""
    resource_type: Optional[str] = None
    resource_amount: float = 0.0
    context: Dict[str, Any] = field(default_factory=dict)
    requested_at: datetime = field(default_factory=datetime.utcnow)
    granted_by: Optional[str] = None  # Grant ID or "human_approval"
    status: str = "pending"  # pending, granted, denied, requires_human
    decision_at: Optional[datetime] = None


class CredentialVault:
    """
    Secure storage for credentials.
    In production, this would use proper encryption and secret management.
    """
    
    def __init__(self, data_dir: str = "./data"):
        self.data_dir = data_dir
        self.credentials: Dict[str, Credential] = {}
        self._ensure_data_dir()
        self._load_state()
    
    def _ensure_data_dir(self):
        """Ensure data directory exists."""
        os.makedirs(self.data_dir, exist_ok=True)
    
    def _get_state_file(self) -> str:
        """Get path to state file."""
        return os.path.join(self.data_dir, "credentials.json")
    
    def _save_state(self):
        """Save credentials to JSON file."""
        filepath = self._get_state_file()
        data = {
            k: self._serialize_credential(v)
            for k, v in self.credentials.items()
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def _load_state(self):
        """Load credentials from JSON file."""
        filepath = self._get_state_file()
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                data = json.load(f)
                for key, value in data.items():
                    self.credentials[key] = self._deserialize_credential(value)
    
    def _serialize_credential(self, cred: Credential) -> Dict:
        """Serialize credential to dictionary."""
        data = cred.__dict__.copy()
        for k, v in data.items():
            if isinstance(v, datetime):
                data[k] = v.isoformat()
        return data
    
    def _deserialize_credential(self, data: Dict) -> Credential:
        """Deserialize dictionary to credential."""
        for field_name in ('created_at', 'last_used_at', 'expires_at'):
            if field_name in data and isinstance(data[field_name], str):
                data[field_name] = datetime.fromisoformat(data[field_name])
        return Credential(**{k: v for k, v in data.items()})
    
    def store_credential(self, credential: Credential):
        """Store a credential."""
        self.credentials[credential.id] = credential
        self._save_state()
    
    def get_credential(self, credential_id: str) -> Optional[Credential]:
        """Get credential by ID."""
        return self.credentials.get(credential_id)
    
    def list_credentials(self, organization_id: Optional[str] = None) -> List[Credential]:
        """List credentials with optional filter."""
        creds = list(self.credentials.values())
        if organization_id:
            creds = [c for c in creds if c.organization_id == organization_id]
        return creds
    
    def invalidate_credential(self, credential_id: str):
        """Invalidate a credential."""
        cred = self.get_credential(credential_id)
        if cred:
            cred.invalidate()
            self._save_state()


class AuthorityService:
    """
    Main authority service for managing grants and verifying operations.
    """
    
    def __init__(self, data_dir: str = "./data"):
        self.data_dir = data_dir
        self.grants: Dict[str, StandingGrant] = {}
        self.requests: Dict[str, AuthorityRequest] = {}
        self.vault = CredentialVault(data_dir)
        self._ensure_data_dir()
        self._load_state()
    
    def _ensure_data_dir(self):
        """Ensure data directory exists."""
        os.makedirs(self.data_dir, exist_ok=True)
    
    def _get_state_file(self) -> str:
        """Get path to state file."""
        return os.path.join(self.data_dir, "authority.json")
    
    def _save_state(self):
        """Save state to JSON file."""
        filepath = self._get_state_file()
        data = {
            'grants': {k: self._serialize_grant(v) for k, v in self.grants.items()},
            'requests': {k: self._serialize_request(v) for k, v in self.requests.items()}
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def _load_state(self):
        """Load state from JSON file."""
        filepath = self._get_state_file()
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                data = json.load(f)
                for key, value in data.get('grants', {}).items():
                    self.grants[key] = self._deserialize_grant(value)
                for key, value in data.get('requests', {}).items():
                    self.requests[key] = self._deserialize_request(value)
    
    def _serialize_grant(self, grant: StandingGrant) -> Dict:
        """Serialize grant to dictionary."""
        data = grant.__dict__.copy()
        data['grant_type'] = grant.grant_type.value
        data['authority_level'] = grant.authority_level.value
        for k, v in data.items():
            if isinstance(v, datetime):
                data[k] = v.isoformat()
        return data
    
    def _deserialize_grant(self, data: Dict) -> StandingGrant:
        """Deserialize dictionary to grant."""
        data['grant_type'] = GrantType(data['grant_type'])
        data['authority_level'] = AuthorityLevel(data['authority_level'])
        for field_name in ('created_at', 'expires_at', 'revoked_at'):
            if field_name in data and isinstance(data[field_name], str):
                data[field_name] = datetime.fromisoformat(data[field_name])
        return StandingGrant(**{k: v for k, v in data.items()})
    
    def _serialize_request(self, req: AuthorityRequest) -> Dict:
        """Serialize request to dictionary."""
        data = req.__dict__.copy()
        for k, v in data.items():
            if isinstance(v, datetime):
                data[k] = v.isoformat()
        return data
    
    def _deserialize_request(self, data: Dict) -> AuthorityRequest:
        """Deserialize dictionary to request."""
        for field_name in ('requested_at', 'decision_at'):
            if field_name in data and isinstance(data[field_name], str):
                data[field_name] = datetime.fromisoformat(data[field_name])
        return AuthorityRequest(**{k: v for k, v in data.items()})
    
    def create_grant(
        self,
        organization_id: str,
        grant_type: GrantType,
        name: str,
        description: str,
        authority_level: AuthorityLevel = AuthorityLevel.AUTONOMOUS,
        resource_limits: Optional[Dict[str, float]] = None,
        allowed_operations: Optional[List[str]] = None,
        denied_operations: Optional[List[str]] = None,
        conditions: Optional[Dict[str, Any]] = None,
        expires_at: Optional[datetime] = None
    ) -> StandingGrant:
        """Create a new standing grant."""
        grant = StandingGrant(
            organization_id=organization_id,
            grant_type=grant_type,
            name=name,
            description=description,
            authority_level=authority_level,
            resource_limits=resource_limits or {},
            allowed_operations=allowed_operations or [],
            denied_operations=denied_operations or [],
            conditions=conditions or {},
            expires_at=expires_at
        )
        self.grants[grant.id] = grant
        self._save_state()
        return grant
    
    def get_grant(self, grant_id: str) -> Optional[StandingGrant]:
        """Get grant by ID."""
        return self.grants.get(grant_id)
    
    def list_grants(self, organization_id: Optional[str] = None, active_only: bool = True) -> List[StandingGrant]:
        """List grants with optional filters."""
        grants = list(self.grants.values())
        if organization_id:
            grants = [g for g in grants if g.organization_id == organization_id]
        if active_only:
            grants = [g for g in grants if g.is_active]
        return grants
    
    def revoke_grant(self, grant_id: str):
        """Revoke a grant."""
        grant = self.get_grant(grant_id)
        if grant:
            grant.revoke()
            self._save_state()
    
    def verify_authority(
        self,
        organization_id: str,
        operation: str,
        resource_type: Optional[str] = None,
        resource_amount: float = 0.0
    ) -> tuple[bool, Optional[str], AuthorityLevel]:
        """
        Verify if an operation is authorized.
        
        Returns:
            (is_authorized, grant_id_or_reason, authority_level)
        """
        active_grants = [g for g in self.grants.values() 
                        if g.organization_id == organization_id and g.is_active]
        
        for grant in active_grants:
            # Check expiration
            if grant.expires_at and datetime.utcnow() > grant.expires_at:
                continue
            
            # Check operation is allowed
            if not grant.is_operation_allowed(operation):
                continue
            
            # Check resource limits
            if resource_type and not grant.check_resource_limit(resource_type, resource_amount):
                continue
            
            # Found matching grant
            return True, grant.id, grant.authority_level
        
        # No matching grant found - check if human-only operation
        human_only_operations = ['legal_attestation', 'binding_signature', 'kyc_verification']
        if operation in human_only_operations:
            return False, "Requires human participation", AuthorityLevel.HUMAN_ONLY
        
        return False, "No standing grant covers this operation", AuthorityLevel.APPROVAL_REQUIRED
    
    def request_authority(
        self,
        organization_id: str,
        operation: str,
        resource_type: Optional[str] = None,
        resource_amount: float = 0.0,
        context: Optional[Dict[str, Any]] = None
    ) -> AuthorityRequest:
        """Create an authority request."""
        is_authorized, result, level = self.verify_authority(
            organization_id, operation, resource_type, resource_amount
        )
        
        request = AuthorityRequest(
            organization_id=organization_id,
            operation=operation,
            resource_type=resource_type,
            resource_amount=resource_amount,
            context=context or {}
        )
        
        if is_authorized:
            request.status = "granted"
            request.granted_by = result  # grant_id
            request.decision_at = datetime.utcnow()
        elif level == AuthorityLevel.HUMAN_ONLY:
            request.status = "requires_human"
            request.decision_at = datetime.utcnow()
        else:
            request.status = "denied"
            request.decision_at = datetime.utcnow()
        
        self.requests[request.id] = request
        self._save_state()
        return request
    
    def approve_request(self, request_id: str, approver: str = "human"):
        """Approve an authority request."""
        request = self.requests.get(request_id)
        if request and request.status == "pending":
            request.status = "granted"
            request.granted_by = approver
            request.decision_at = datetime.utcnow()
            self._save_state()
    
    def deny_request(self, request_id: str, reason: str = ""):
        """Deny an authority request."""
        request = self.requests.get(request_id)
        if request and request.status == "pending":
            request.status = "denied"
            request.context["denial_reason"] = reason
            request.decision_at = datetime.utcnow()
            self._save_state()
    
    def store_credential(self, organization_id: str, grant_id: str, service_name: str, 
                        credential_type: str, encrypted_data: Dict[str, str],
                        metadata: Optional[Dict[str, Any]] = None,
                        expires_at: Optional[datetime] = None) -> Credential:
        """Store a credential in the vault."""
        credential = Credential(
            organization_id=organization_id,
            grant_id=grant_id,
            service_name=service_name,
            credential_type=credential_type,
            encrypted_data=encrypted_data,
            metadata=metadata or {},
            expires_at=expires_at
        )
        self.vault.store_credential(credential)
        return credential
    
    def get_credential(self, credential_id: str) -> Optional[Credential]:
        """Get credential from vault."""
        return self.vault.get_credential(credential_id)
    
    def rotate_credential(self, credential_id: str, new_encrypted_data: Dict[str, str]):
        """Rotate a credential."""
        credential = self.vault.get_credential(credential_id)
        if credential:
            credential.encrypted_data = new_encrypted_data
            credential.last_used_at = datetime.utcnow()
            self.vault._save_state()
    
    def get_pending_requests(self, organization_id: Optional[str] = None) -> List[AuthorityRequest]:
        """Get pending authority requests."""
        requests = [r for r in self.requests.values() if r.status == "pending"]
        if organization_id:
            requests = [r for r in requests if r.organization_id == organization_id]
        return requests
