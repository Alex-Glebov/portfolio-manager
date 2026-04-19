"""
CSV Database Helper - Portfolio Manager

All database operations implemented using CSV files.
This module provides a controlled interface for data persistence.
Supports multiple portfolios with separate data directories.
"""
import csv
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)

# Default paths
DATA_DIR = Path("data")
USERS_FILE = DATA_DIR / "users.csv"

# Portfolio support - each portfolio has its own subdirectory
DEFAULT_PORTFOLIO = ""  # Empty string represents default portfolio


def _get_portfolio_dir(portfolio: str = DEFAULT_PORTFOLIO) -> Path:
    """Get data directory for a portfolio"""
    if portfolio and portfolio != DEFAULT_PORTFOLIO:
        return DATA_DIR / portfolio
    return DATA_DIR


def _get_transactions_file(portfolio: str = DEFAULT_PORTFOLIO) -> Path:
    """Get transactions file path for a portfolio"""
    return _get_portfolio_dir(portfolio) / "transactions.csv"


def _get_backup_dir(portfolio: str = DEFAULT_PORTFOLIO) -> Path:
    """Get backup directory for a portfolio"""
    return _get_portfolio_dir(portfolio) / "backups"


def _ensure_data_dir(portfolio: str = DEFAULT_PORTFOLIO):
    """Ensure data directory exists for a portfolio"""
    portfolio_dir = _get_portfolio_dir(portfolio)
    portfolio_dir.mkdir(parents=True, exist_ok=True)
    _get_backup_dir(portfolio).mkdir(parents=True, exist_ok=True)
    # Also ensure base data dir and users file exist
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _read_csv(filepath: Path) -> List[Dict[str, Any]]:
    """Read CSV file and return list of dictionaries"""
    if not filepath.exists():
        logger.warning(f"CSV file not found: {filepath}. Returning empty list.")
        return []

    try:
        with open(filepath, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            logger.debug(f"Read {len(rows)} rows from {filepath}")
            return rows
    except Exception as e:
        logger.error(f"Error reading CSV file {filepath}: {e}")
        raise


def _write_csv(filepath: Path, data: List[Dict[str, Any]], fieldnames: List[str], portfolio: str = DEFAULT_PORTFOLIO):
    """Write list of dictionaries to CSV file"""
    _ensure_data_dir(portfolio)

    # Create backup if file exists
    if filepath.exists():
        _backup_file(filepath, portfolio)

    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
            logger.debug(f"Wrote {len(data)} rows to {filepath}")
    except Exception as e:
        logger.error(f"Error writing CSV file {filepath}: {e}")
        raise


def _backup_file(filepath: Path, portfolio: str = DEFAULT_PORTFOLIO):
    """Create timestamped backup of file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{filepath.stem}_{timestamp}{filepath.suffix}"
    backup_path = _get_backup_dir(portfolio) / backup_name
    try:
        shutil.copy2(filepath, backup_path)
        logger.info(f"Created backup: {backup_path}")
    except Exception as e:
        logger.warning(f"Failed to create backup for {filepath}: {e}")


def _convert_types(row: Dict[str, Any], schema: Dict[str, type]) -> Dict[str, Any]:
    """Convert string values to appropriate types based on schema"""
    converted = {}
    for key, value in row.items():
        if key in schema and value is not None and value != '':
            try:
                if schema[key] == bool:
                    converted[key] = value.lower() in ('true', '1', 'yes', 'on')
                elif schema[key] == datetime:
                    converted[key] = datetime.fromisoformat(value)
                else:
                    converted[key] = schema[key](value)
            except (ValueError, TypeError) as e:
                logger.warning(f"Type conversion failed for {key}='{value}': {e}. Using as string.")
                converted[key] = value
        else:
            converted[key] = value
    return converted


# Transaction Schema
TRANSACTION_SCHEMA = {
    'id': int,
    'timestamp': datetime,
    'name': str,
    'cost': float,
    'qty': float,
    'cost_units': str,
    'direction': str,
    'counterpart_id': str,
    'notes': str,
    'total_value': float
}

TRANSACTION_FIELDS = list(TRANSACTION_SCHEMA.keys())


# User Schema
USER_SCHEMA = {
    'id': int,
    'username': str,
    'hashed_password': str,
    'is_active': bool,
    'created_at': datetime
}

USER_FIELDS = list(USER_SCHEMA.keys())


# =============================================================================
# TRANSACTION OPERATIONS
# =============================================================================

def init_transactions(portfolio: str = DEFAULT_PORTFOLIO) -> bool:
    """Initialize transactions CSV with headers if not exists"""
    _ensure_data_dir(portfolio)
    transactions_file = _get_transactions_file(portfolio)
    if not transactions_file.exists():
        _write_csv(transactions_file, [], TRANSACTION_FIELDS, portfolio)
        logger.info(f"Initialized transactions database: {transactions_file}")
        return True
    return False


def get_all_transactions(portfolio: str = DEFAULT_PORTFOLIO) -> List[Dict[str, Any]]:
    """Get all transactions from CSV for a portfolio"""
    init_transactions(portfolio)
    transactions_file = _get_transactions_file(portfolio)
    rows = _read_csv(transactions_file)
    return [_convert_types(row, TRANSACTION_SCHEMA) for row in rows]


def get_transaction_by_id(transaction_id: int, portfolio: str = DEFAULT_PORTFOLIO) -> Optional[Dict[str, Any]]:
    """Get single transaction by ID from a portfolio"""
    transactions = get_all_transactions(portfolio)
    for txn in transactions:
        if int(txn.get('id', 0)) == transaction_id:
            return txn
    logger.warning(f"Transaction with id {transaction_id} not found in portfolio '{portfolio}'")
    return None


def create_transaction(transaction_data: Dict[str, Any], portfolio: str = DEFAULT_PORTFOLIO) -> Dict[str, Any]:
    """Create new transaction and append to CSV in a portfolio"""
    transactions = get_all_transactions(portfolio)

    # Auto-assign ID if not provided
    if 'id' not in transaction_data or transaction_data['id'] is None:
        max_id = max([int(t.get('id', 0)) for t in transactions], default=0)
        transaction_data['id'] = max_id + 1
        logger.debug(f"Auto-assigned transaction ID: {transaction_data['id']}")

    # Ensure timestamp
    if 'timestamp' not in transaction_data or transaction_data['timestamp'] is None:
        transaction_data['timestamp'] = datetime.utcnow()
        logger.debug(f"Auto-assigned timestamp: {transaction_data['timestamp']}")

    # Calculate total_value if not provided
    if 'total_value' not in transaction_data or transaction_data['total_value'] is None:
        try:
            cost = float(transaction_data.get('cost', 0))
            qty = float(transaction_data.get('qty', 0))
            transaction_data['total_value'] = cost * qty
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not calculate total_value: {e}. Setting to 0.")
            transaction_data['total_value'] = 0

    # Convert datetime to ISO string for CSV storage
    if isinstance(transaction_data.get('timestamp'), datetime):
        transaction_data['timestamp'] = transaction_data['timestamp'].isoformat()

    transactions.append(transaction_data)
    transactions_file = _get_transactions_file(portfolio)
    _write_csv(transactions_file, transactions, TRANSACTION_FIELDS, portfolio)
    logger.info(f"Created transaction ID {transaction_data['id']} in portfolio '{portfolio}'")
    return transaction_data


def update_transaction(transaction_id: int, updates: Dict[str, Any], portfolio: str = DEFAULT_PORTFOLIO) -> Optional[Dict[str, Any]]:
    """Update existing transaction in a portfolio"""
    transactions = get_all_transactions(portfolio)

    for i, txn in enumerate(transactions):
        if int(txn.get('id', 0)) == transaction_id:
            # Merge updates
            for key, value in updates.items():
                if key in TRANSACTION_FIELDS:
                    if key == 'timestamp' and isinstance(value, datetime):
                        value = value.isoformat()
                    txn[key] = value

            # Recalculate total_value if cost or qty changed
            if 'cost' in updates or 'qty' in updates:
                try:
                    cost = float(txn.get('cost', 0))
                    qty = float(txn.get('qty', 0))
                    txn['total_value'] = cost * qty
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not recalculate total_value: {e}")

            transactions[i] = txn
            transactions_file = _get_transactions_file(portfolio)
            _write_csv(transactions_file, transactions, TRANSACTION_FIELDS, portfolio)
            logger.info(f"Updated transaction ID {transaction_id} in portfolio '{portfolio}'")
            return txn

    logger.warning(f"Cannot update: Transaction with id {transaction_id} not found in portfolio '{portfolio}'")
    return None


def delete_transaction(transaction_id: int, portfolio: str = DEFAULT_PORTFOLIO) -> bool:
    """Delete transaction by ID from a portfolio"""
    transactions = get_all_transactions(portfolio)
    original_count = len(transactions)
    transactions = [t for t in transactions if int(t.get('id', 0)) != transaction_id]

    if len(transactions) == original_count:
        logger.warning(f"Cannot delete: Transaction with id {transaction_id} not found in portfolio '{portfolio}'")
        return False

    transactions_file = _get_transactions_file(portfolio)
    _write_csv(transactions_file, transactions, TRANSACTION_FIELDS, portfolio)
    logger.info(f"Deleted transaction ID {transaction_id} from portfolio '{portfolio}'")
    return True


def filter_transactions(
    name: Optional[str] = None,
    direction: Optional[str] = None,
    counterpart_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    portfolio: str = DEFAULT_PORTFOLIO
) -> List[Dict[str, Any]]:
    """Filter transactions with pagination from a portfolio"""
    transactions = get_all_transactions(portfolio)

    if name:
        transactions = [t for t in transactions if t.get('name') == name]
    if direction:
        transactions = [t for t in transactions if t.get('direction') == direction]
    if counterpart_id:
        transactions = [t for t in transactions if t.get('counterpart_id') == counterpart_id]

    # Sort by timestamp descending
    def get_timestamp(t):
        ts = t.get('timestamp')
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts)
            except ValueError:
                return datetime.min
        return ts if isinstance(ts, datetime) else datetime.min

    transactions = sorted(transactions, key=get_timestamp, reverse=True)

    # Apply pagination
    return transactions[offset:offset + limit]


# =============================================================================
# USER OPERATIONS (for authentication)
# =============================================================================

def init_users() -> bool:
    """Initialize users CSV with headers if not exists"""
    _ensure_data_dir()
    if not USERS_FILE.exists():
        _write_csv(USERS_FILE, [], USER_FIELDS)
        logger.info(f"Initialized users database: {USERS_FILE}")
        return True
    return False


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Get user by username"""
    init_users()
    rows = _read_csv(USERS_FILE)
    for row in rows:
        if row.get('username') == username:
            return _convert_types(row, USER_SCHEMA)
    return None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user by ID"""
    init_users()
    rows = _read_csv(USERS_FILE)
    for row in rows:
        if int(row.get('id', 0)) == user_id:
            return _convert_types(row, USER_SCHEMA)
    return None


def create_user(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create new user"""
    users = _read_csv(USERS_FILE)

    # Check for duplicate username
    if any(u.get('username') == user_data.get('username') for u in users):
        raise ValueError(f"Username '{user_data['username']}' already exists")

    # Auto-assign ID
    if 'id' not in user_data or user_data['id'] is None:
        max_id = max([int(u.get('id', 0)) for u in users], default=0)
        user_data['id'] = max_id + 1

    # Ensure created_at
    if 'created_at' not in user_data or user_data['created_at'] is None:
        user_data['created_at'] = datetime.utcnow()

    if isinstance(user_data.get('created_at'), datetime):
        user_data['created_at'] = user_data['created_at'].isoformat()

    users.append(user_data)
    _write_csv(USERS_FILE, users, USER_FIELDS)
    logger.info(f"Created user: {user_data['username']} (ID: {user_data['id']})")
    return user_data


def update_user(user_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update user data"""
    users = _read_csv(USERS_FILE)

    for i, user in enumerate(users):
        if int(user.get('id', 0)) == user_id:
            for key, value in updates.items():
                if key in USER_FIELDS:
                    if key == 'created_at' and isinstance(value, datetime):
                        value = value.isoformat()
                    user[key] = value
            users[i] = user
            _write_csv(USERS_FILE, users, USER_FIELDS)
            logger.info(f"Updated user ID {user_id}")
            return user

    return None


# =============================================================================
# CSV EXPORT
# =============================================================================

def export_transactions_to_csv(filepath: Path, portfolio: str = DEFAULT_PORTFOLIO) -> Path:
    """Export all transactions to CSV file from a portfolio"""
    transactions = get_all_transactions(portfolio)

    # Convert datetime objects back to strings for export
    export_data = []
    for txn in transactions:
        export_txn = dict(txn)
        if isinstance(export_txn.get('timestamp'), datetime):
            export_txn['timestamp'] = export_txn['timestamp'].isoformat()
        export_data.append(export_txn)

    _write_csv(filepath, export_data, TRANSACTION_FIELDS, portfolio)
    logger.info(f"Exported {len(transactions)} transactions to {filepath} from portfolio '{portfolio}'")
    return filepath


def export_holdings_to_csv(filepath: Path, holdings: List[Dict[str, Any]]) -> Path:
    """Export holdings summary to CSV"""
    if not holdings:
        logger.warning("No holdings to export")
        _write_csv(filepath, [], [])
        return filepath

    fieldnames = list(holdings[0].keys())
    _write_csv(filepath, holdings, fieldnames)
    logger.info(f"Exported {len(holdings)} holdings to {filepath}")
    return filepath


# =============================================================================
# DATA MIGRATION / INITIAL LOAD
# =============================================================================

def load_initial_transactions_from_csv(filepath: Path, append: bool = False) -> int:
    """Load initial transactions from external CSV file"""
    if not filepath.exists():
        logger.error(f"Initial data file not found: {filepath}")
        raise FileNotFoundError(f"File not found: {filepath}")

    rows = _read_csv(filepath)
    if not rows:
        logger.warning(f"No data found in {filepath}")
        return 0

    if not append:
        # Clear existing
        _write_csv(TRANSACTIONS_FILE, [], TRANSACTION_FIELDS)
        logger.info("Cleared existing transactions before import")

    count = 0
    for row in rows:
        try:
            # Map common field names to our schema
            mapped_row = {}
            field_mapping = {
                'item_name': 'name',
                'item': 'name',
                'price': 'cost',
                'amount': 'qty',
                'quantity': 'qty',
                'currency': 'cost_units',
                'unit': 'cost_units',
                'source': 'counterpart_id',
                'destination': 'counterpart_id',
                'src_dest': 'counterpart_id'
            }

            for key, value in row.items():
                mapped_key = field_mapping.get(key.lower(), key)
                if mapped_key in TRANSACTION_FIELDS:
                    mapped_row[mapped_key] = value

            create_transaction(mapped_row)
            count += 1
        except Exception as e:
            logger.error(f"Error importing row {row}: {e}")

    logger.info(f"Loaded {count} initial transactions from {filepath}")
    return count
