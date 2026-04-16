"""
Database Helper Abstraction Layer

This module provides a unified interface for database operations.
Currently uses CSV backend (helper_csv).
When ready to switch to a real database, replace the import below.

Usage:
    from helper_database import (
        init_database,
        get_all_transactions,
        create_transaction,
        get_user_by_username,
        ...
    )
"""

# =============================================================================
# BACKEND SELECTION
# =============================================================================
# To switch to a real database, change this import:
# from helper_db import *
# And implement all the same functions in helper_db.py

from helper_csv import (
    # Transaction operations
    init_transactions,
    get_all_transactions,
    get_transaction_by_id,
    create_transaction,
    update_transaction,
    delete_transaction,
    filter_transactions,

    # User operations
    init_users,
    get_user_by_username,
    get_user_by_id,
    create_user,
    update_user,

    # Export operations
    export_transactions_to_csv,
    export_holdings_to_csv,

    # Import operations
    load_initial_transactions_from_csv,

    # Constants
    DATA_DIR,
    TRANSACTIONS_FILE,
    USERS_FILE,
    BACKUP_DIR,
)

import logging

logger = logging.getLogger(__name__)

# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def init_database():
    """Initialize all database components"""
    init_transactions()
    init_users()
    logger.info("Database initialized successfully")


def get_next_transaction_id() -> int:
    """Get next available transaction ID"""
    transactions = get_all_transactions()
    if not transactions:
        return 1
    return max(int(t.get('id', 0)) for t in transactions) + 1


def get_transaction_count() -> int:
    """Get total number of transactions"""
    return len(get_all_transactions())


def transaction_exists(transaction_id: int) -> bool:
    """Check if transaction exists"""
    return get_transaction_by_id(transaction_id) is not None


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Initialization
    'init_database',
    'init_transactions',
    'init_users',

    # Transaction operations
    'get_all_transactions',
    'get_transaction_by_id',
    'create_transaction',
    'update_transaction',
    'delete_transaction',
    'filter_transactions',
    'get_next_transaction_id',
    'get_transaction_count',
    'transaction_exists',

    # User operations
    'get_user_by_username',
    'get_user_by_id',
    'create_user',
    'update_user',

    # Export operations
    'export_transactions_to_csv',
    'export_holdings_to_csv',

    # Import operations
    'load_initial_transactions_from_csv',

    # Constants
    'DATA_DIR',
    'TRANSACTIONS_FILE',
    'USERS_FILE',
    'BACKUP_DIR',
]
