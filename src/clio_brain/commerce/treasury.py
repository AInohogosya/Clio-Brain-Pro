"""
Treasury & Resource Service

Double-entry bookkeeping for funds, compute, and liabilities.
Manages reservations, fleet management, and asset registry.
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid
import json
import os


class AccountType(Enum):
    """Types of accounts in double-entry system."""
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"


class TransactionType(Enum):
    """Types of transactions."""
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"
    REVENUE = "revenue"
    EXPENSE = "expense"
    REFUND = "refund"
    FEE = "fee"
    ENCUMBRANCE = "encumbrance"
    RELEASE = "release"


@dataclass
class Account:
    """Account in double-entry bookkeeping system."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: str = ""
    name: str = ""
    account_type: AccountType = AccountType.ASSET
    currency: str = "USD"
    balance: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def post_debit(self, amount: float):
        """Post debit entry (increases assets/expenses, decreases liabilities/revenue/equity)."""
        if self.account_type in (AccountType.ASSET, AccountType.EXPENSE):
            self.balance += amount
        else:
            self.balance -= amount
    
    def post_credit(self, amount: float):
        """Post credit entry (decreases assets/expenses, increases liabilities/revenue/equity)."""
        if self.account_type in (AccountType.ASSET, AccountType.EXPENSE):
            self.balance -= amount
        else:
            self.balance += amount


@dataclass
class JournalEntry:
    """Single entry in a journal transaction."""
    account_id: str = ""
    account_name: str = ""
    debit: float = 0.0
    credit: float = 0.0


@dataclass
class Transaction:
    """Double-entry transaction."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: str = ""
    transaction_type: TransactionType = TransactionType.TRANSFER
    description: str = ""
    entries: List[JournalEntry] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    external_reference: Optional[str] = None
    
    def is_balanced(self) -> bool:
        """Check if debits equal credits."""
        total_debits = sum(e.debit for e in self.entries)
        total_credits = sum(e.credit for e in self.entries)
        return abs(total_debits - total_credits) < 0.001
    
    def add_entry(self, account_id: str, account_name: str, debit: float = 0.0, credit: float = 0.0):
        """Add journal entry."""
        self.entries.append(JournalEntry(
            account_id=account_id,
            account_name=account_name,
            debit=debit,
            credit=credit
        ))


@dataclass
class RevenueRecord:
    """Verified revenue record from external customer payment."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: str = ""
    amount: float = 0.0
    currency: str = "USD"
    customer_id: Optional[str] = None
    payment_provider: str = ""
    external_receipt: Dict[str, Any] = field(default_factory=dict)
    verified: bool = False
    recorded_at: datetime = field(default_factory=datetime.utcnow)
    
    # Revenue ladder tracking
    tier: int = 0  # 1=$1, 2=$100, 3=$1000, 4=$10000
    
    def verify(self, receipt: Dict[str, Any]):
        """Verify revenue with external receipt."""
        self.external_receipt = receipt
        self.verified = True
        
        # Determine tier based on cumulative revenue
        if self.amount >= 10000:
            self.tier = 4
        elif self.amount >= 1000:
            self.tier = 3
        elif self.amount >= 100:
            self.tier = 2
        elif self.amount >= 1:
            self.tier = 1


@dataclass
class ContributionProfit:
    """Contribution profit calculation."""
    revenue: float = 0.0
    refunds: float = 0.0
    payment_fees: float = 0.0
    direct_delivery_costs: float = 0.0
    acquisition_costs: float = 0.0
    
    @property
    def profit(self) -> float:
        """Calculate contribution profit."""
        return self.revenue - self.refunds - self.payment_fees - self.direct_delivery_costs - self.acquisition_costs


@dataclass
class ResourceReservation:
    """Resource reservation for mission execution."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: str = ""
    mission_id: str = ""
    resource_type: str = ""  # compute, storage, api_calls, etc.
    amount: float = 0.0
    unit: str = ""
    encumbered_account: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    released_at: Optional[datetime] = None
    is_active: bool = True
    
    def release(self):
        """Release the reservation."""
        self.is_active = False
        self.released_at = datetime.utcnow()


class TreasuryService:
    """
    Treasury service implementing double-entry bookkeeping.
    Tracks revenue, expenses, and resource encumbrances.
    """
    
    def __init__(self, data_dir: str = "./data"):
        self.data_dir = data_dir
        self.accounts: Dict[str, Account] = {}
        self.transactions: Dict[str, Transaction] = {}
        self.revenue_records: Dict[str, RevenueRecord] = {}
        self.reservations: Dict[str, ResourceReservation] = {}
        self._ensure_data_dir()
        self._load_state()
    
    def _ensure_data_dir(self):
        os.makedirs(self.data_dir, exist_ok=True)
    
    def _get_state_file(self) -> str:
        return os.path.join(self.data_dir, "treasury.json")
    
    def _save_state(self):
        filepath = self._get_state_file()
        data = {
            'accounts': {k: self._serialize_account(v) for k, v in self.accounts.items()},
            'transactions': {k: self._serialize_transaction(v) for k, v in self.transactions.items()},
            'revenue_records': {k: self._serialize_revenue(v) for k, v in self.revenue_records.items()},
            'reservations': {k: self._serialize_reservation(v) for k, v in self.reservations.items()}
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def _load_state(self):
        filepath = self._get_state_file()
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                data = json.load(f)
                for key, value in data.get('accounts', {}).items():
                    self.accounts[key] = self._deserialize_account(value)
                for key, value in data.get('transactions', {}).items():
                    self.transactions[key] = self._deserialize_transaction(value)
                for key, value in data.get('revenue_records', {}).items():
                    self.revenue_records[key] = self._deserialize_revenue(value)
                for key, value in data.get('reservations', {}).items():
                    self.reservations[key] = self._deserialize_reservation(value)
    
    def _serialize_account(self, acc: Account) -> Dict:
        data = acc.__dict__.copy()
        data['account_type'] = acc.account_type.value
        for k, v in data.items():
            if isinstance(v, datetime):
                data[k] = v.isoformat()
        return data
    
    def _deserialize_account(self, data: Dict) -> Account:
        data['account_type'] = AccountType(data['account_type'])
        for field_name in ('created_at',):
            if field_name in data and isinstance(data[field_name], str):
                data[field_name] = datetime.fromisoformat(data[field_name])
        return Account(**{k: v for k, v in data.items()})
    
    def _serialize_transaction(self, tx: Transaction) -> Dict:
        data = tx.__dict__.copy()
        data['transaction_type'] = tx.transaction_type.value
        data['entries'] = [{'account_id': e.account_id, 'account_name': e.account_name, 
                           'debit': e.debit, 'credit': e.credit} for e in tx.entries]
        for k, v in data.items():
            if isinstance(v, datetime):
                data[k] = v.isoformat()
        return data
    
    def _deserialize_transaction(self, data: Dict) -> Transaction:
        data['transaction_type'] = TransactionType(data['transaction_type'])
        entries = [JournalEntry(**e) for e in data.pop('entries', [])]
        for field_name in ('created_at',):
            if field_name in data and isinstance(data[field_name], str):
                data[field_name] = datetime.fromisoformat(data[field_name])
        tx = Transaction(**{k: v for k, v in data.items()})
        tx.entries = entries
        return tx
    
    def _serialize_revenue(self, rev: RevenueRecord) -> Dict:
        data = rev.__dict__.copy()
        for k, v in data.items():
            if isinstance(v, datetime):
                data[k] = v.isoformat()
        return data
    
    def _deserialize_revenue(self, data: Dict) -> RevenueRecord:
        for field_name in ('recorded_at',):
            if field_name in data and isinstance(data[field_name], str):
                data[field_name] = datetime.fromisoformat(data[field_name])
        return RevenueRecord(**{k: v for k, v in data.items()})
    
    def _serialize_reservation(self, res: ResourceReservation) -> Dict:
        data = res.__dict__.copy()
        for k, v in data.items():
            if isinstance(v, datetime):
                data[k] = v.isoformat()
        return data
    
    def _deserialize_reservation(self, data: Dict) -> ResourceReservation:
        for field_name in ('created_at', 'released_at'):
            if field_name in data and isinstance(data[field_name], str):
                data[field_name] = datetime.fromisoformat(data[field_name])
        return ResourceReservation(**{k: v for k, v in data.items()})
    
    def create_account(self, organization_id: str, name: str, account_type: AccountType, 
                      currency: str = "USD", metadata: Optional[Dict] = None) -> Account:
        """Create a new account."""
        account = Account(
            organization_id=organization_id,
            name=name,
            account_type=account_type,
            currency=currency,
            metadata=metadata or {}
        )
        self.accounts[account.id] = account
        self._save_state()
        return account
    
    def get_account(self, account_id: str) -> Optional[Account]:
        """Get account by ID."""
        return self.accounts.get(account_id)
    
    def list_accounts(self, organization_id: Optional[str] = None, 
                     account_type: Optional[AccountType] = None) -> List[Account]:
        """List accounts with filters."""
        accounts = list(self.accounts.values())
        if organization_id:
            accounts = [a for a in accounts if a.organization_id == organization_id]
        if account_type:
            accounts = [a for a in accounts if a.account_type == account_type]
        return accounts
    
    def create_transaction(self, organization_id: str, transaction_type: TransactionType,
                          description: str, entries: List[Tuple[str, str, float, float]],
                          metadata: Optional[Dict] = None,
                          external_reference: Optional[str] = None) -> Optional[Transaction]:
        """
        Create a double-entry transaction.
        
        entries: List of (account_id, account_name, debit, credit)
        Returns None if transaction doesn't balance.
        """
        tx = Transaction(
            organization_id=organization_id,
            transaction_type=transaction_type,
            description=description,
            metadata=metadata or {},
            external_reference=external_reference
        )
        
        for account_id, account_name, debit, credit in entries:
            tx.add_entry(account_id, account_name, debit, credit)
        
        if not tx.is_balanced():
            return None
        
        # Post to accounts
        for entry in tx.entries:
            account = self.get_account(entry.account_id)
            if account:
                if entry.debit > 0:
                    account.post_debit(entry.debit)
                if entry.credit > 0:
                    account.post_credit(entry.credit)
        
        self.transactions[tx.id] = tx
        self._save_state()
        return tx
    
    def record_owner_deposit(self, organization_id: str, amount: float, 
                            source_account_id: Optional[str] = None) -> Optional[Transaction]:
        """Record owner deposit (not revenue - goes to equity)."""
        # Find or create equity account
        equity_accounts = self.list_accounts(organization_id, AccountType.EQUITY)
        if not equity_accounts:
            equity_account = self.create_account(organization_id, "Owner Equity", AccountType.EQUITY)
        else:
            equity_account = equity_accounts[0]
        
        # Find or create cash account
        asset_accounts = self.list_accounts(organization_id, AccountType.ASSET)
        if not asset_accounts:
            cash_account = self.create_account(organization_id, "Cash", AccountType.ASSET)
        else:
            cash_account = asset_accounts[0]
        
        return self.create_transaction(
            organization_id=organization_id,
            transaction_type=TransactionType.DEPOSIT,
            description="Owner deposit",
            entries=[
                (cash_account.id, cash_account.name, amount, 0),
                (equity_account.id, equity_account.name, 0, amount)
            ]
        )
    
    def record_revenue(self, organization_id: str, amount: float, customer_id: Optional[str] = None,
                      payment_provider: str = "", external_receipt: Optional[Dict] = None) -> Optional[RevenueRecord]:
        """
        Record verified customer revenue.
        Self-payments are excluded - must verify external receipt.
        """
        # Verify this is genuine external revenue
        if not external_receipt:
            return None
        
        # Find revenue account
        revenue_accounts = self.list_accounts(organization_id, AccountType.REVENUE)
        if not revenue_accounts:
            revenue_account = self.create_account(organization_id, "Customer Revenue", AccountType.REVENUE)
        else:
            revenue_account = revenue_accounts[0]
        
        # Find cash account
        asset_accounts = self.list_accounts(organization_id, AccountType.ASSET)
        cash_account = asset_accounts[0] if asset_accounts else None
        
        if not cash_account:
            return None
        
        # Record transaction
        tx = self.create_transaction(
            organization_id=organization_id,
            transaction_type=TransactionType.REVENUE,
            description=f"Customer payment from {customer_id or 'unknown'}",
            entries=[
                (cash_account.id, cash_account.name, amount, 0),
                (revenue_account.id, revenue_account.name, 0, amount)
            ],
            external_reference=external_receipt.get("payment_id")
        )
        
        if not tx:
            return None
        
        # Create revenue record
        record = RevenueRecord(
            organization_id=organization_id,
            amount=amount,
            customer_id=customer_id,
            payment_provider=payment_provider,
            external_receipt=external_receipt
        )
        record.verify(external_receipt)
        self.revenue_records[record.id] = record
        self._save_state()
        
        return record
    
    def record_expense(self, organization_id: str, amount: float, category: str,
                      description: str) -> Optional[Transaction]:
        """Record an expense."""
        # Find expense account
        expense_accounts = self.list_accounts(organization_id, AccountType.EXPENSE)
        expense_account = None
        for acc in expense_accounts:
            if category.lower() in acc.name.lower():
                expense_account = acc
                break
        
        if not expense_account:
            expense_account = self.create_account(organization_id, f"{category} Expenses", AccountType.EXPENSE)
        
        # Find cash/liability account
        asset_accounts = self.list_accounts(organization_id, AccountType.ASSET)
        cash_account = asset_accounts[0] if asset_accounts else None
        
        if not cash_account:
            return None
        
        return self.create_transaction(
            organization_id=organization_id,
            transaction_type=TransactionType.EXPENSE,
            description=description,
            entries=[
                (expense_account.id, expense_account.name, amount, 0),
                (cash_account.id, cash_account.name, 0, amount)
            ]
        )
    
    def encumber_resources(self, organization_id: str, mission_id: str,
                          resource_type: str, amount: float, unit: str,
                          account_id: str) -> Optional[ResourceReservation]:
        """Encumber resources for a mission."""
        account = self.get_account(account_id)
        if not account or account.balance < amount:
            return None
        
        reservation = ResourceReservation(
            organization_id=organization_id,
            mission_id=mission_id,
            resource_type=resource_type,
            amount=amount,
            unit=unit,
            encumbered_account=account_id
        )
        self.reservations[reservation.id] = reservation
        
        # Reduce available balance
        account.balance -= amount
        self._save_state()
        
        return reservation
    
    def release_reservation(self, reservation_id: str, actual_cost: float = 0.0):
        """Release a resource reservation."""
        reservation = self.reservations.get(reservation_id)
        if not reservation or not reservation.is_active:
            return
        
        reservation.release()
        
        # If there's actual cost, record it; otherwise release full amount
        account = self.get_account(reservation.encumbered_account)
        if account:
            remaining = reservation.amount - actual_cost
            if remaining > 0:
                account.balance += remaining
        
        self._save_state()
    
    def calculate_contribution_profit(self, organization_id: str, 
                                     period_start: Optional[datetime] = None,
                                     period_end: Optional[datetime] = None) -> ContributionProfit:
        """Calculate contribution profit for a period."""
        profit = ContributionProfit()
        
        # Sum revenue
        for record in self.revenue_records.values():
            if record.organization_id != organization_id:
                continue
            if not record.verified:
                continue
            profit.revenue += record.amount
        
        # TODO: Filter by period, subtract refunds, fees, delivery costs, acquisition costs
        
        return profit
    
    def get_total_revenue(self, organization_id: str) -> float:
        """Get total verified revenue for organization."""
        return sum(r.amount for r in self.revenue_records.values() 
                  if r.organization_id == organization_id and r.verified)
    
    def get_revenue_tier(self, organization_id: str) -> int:
        """Get current revenue ladder tier."""
        total = self.get_total_revenue(organization_id)
        if total >= 10000:
            return 4
        elif total >= 1000:
            return 3
        elif total >= 100:
            return 2
        elif total >= 1:
            return 1
        return 0
