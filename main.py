"""
Portfolio Manager API - Resource Accumulation & Warehouse Management

A controlled interface for managing resources with transaction tracking,
CSV persistence, and JWT authentication.

Features:
- Transaction-based resource movements (in/out)
- CSV database with automatic backups
- JWT authentication
- Portfolio holdings calculation
- Initial portfolio loading from CSV
- Comprehensive logging

Configuration priority (highest to lowest):
1. Command line arguments (--host, --port, --user, --password)
2. Environment variables (PORTFOLIO_MANAGER_HOST, PORTFOLIO_MANAGER_PORT, PORTFOLIO_MANAGER_USER, PORTFOLIO_MANAGER_PASSWORD)
3. Config file (config.ini)
4. Default values
"""
import argparse
import logging
import os
import sys
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from __init__ import __version__

# =============================================================================
# Configuration Loading
# =============================================================================

# We need to load config early for CLI parser defaults
from config_handler import (
    DEFAULT_CONFIG_PATH,
    get_api_config,
    load_config,
)


def get_config_with_env():
    """Load config and apply environment variable overrides.

    Priority: Environment variables override config file values.
    """
    # 1. Load config file (base)
    cfg = load_config(DEFAULT_CONFIG_PATH)
    api_cfg = get_api_config(cfg)

    # 2. Apply environment variable overrides (higher priority)
    env_host = os.environ.get('PORTFOLIO_MANAGER_HOST')
    env_port = os.environ.get('PORTFOLIO_MANAGER_PORT')
    env_user = os.environ.get('PORTFOLIO_MANAGER_USER')
    env_password = os.environ.get('PORTFOLIO_MANAGER_PASSWORD')

    if env_host:
        api_cfg['host'] = env_host
    if env_port:
        try:
            api_cfg['port'] = int(env_port)
        except ValueError:
            pass
    if env_user:
        api_cfg['username'] = env_user
    if env_password:
        api_cfg['password'] = env_password

    return cfg, api_cfg


# Load config with env overrides (for CLI defaults)
config, api_config_with_env = get_config_with_env()


# =============================================================================
# Command Line Argument Parsing
# =============================================================================

def parse_cli_args():
    """Parse command line arguments with config+env values as defaults"""
    parser = argparse.ArgumentParser(
        description='Portfolio Manager API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Configuration priority (highest to lowest):
  1. Command line arguments (--host, --port, --user, --password)
  2. Environment variables (PORTFOLIO_MANAGER_HOST, PORTFOLIO_MANAGER_PORT, etc.)
  3. Config file (config.ini)
  4. Default values

Examples:
  python main.py
  python main.py --host 127.0.0.1 --port 9000
  python main.py --user admin --password secret
        """
    )
    parser.add_argument(
        '--host',
        type=str,
        default=api_config_with_env.get('host', '0.0.0.0'),
        help=f"Server host (default: {api_config_with_env.get('host', '0.0.0.0')})"
    )
    parser.add_argument(
        '--port',
        type=int,
        default=api_config_with_env.get('port', 8000),
        help=f"Server port (default: {api_config_with_env.get('port', 8000)})"
    )
    parser.add_argument(
        '--user', '--username',
        dest='username',
        type=str,
        default=api_config_with_env.get('username', ''),
        help='Default admin username'
    )
    parser.add_argument(
        '--password',
        type=str,
        default=api_config_with_env.get('password', ''),
        help='Default admin password'
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}'
    )
    return parser.parse_args()


# Parse CLI args (highest priority)
cli_args = parse_cli_args()

# Local imports
from auth import (
    Token,
    User,
    UserCreate,
    check_auth_enabled,
    create_admin_user,
    get_current_active_user,
    handle_login,
    register_user,
)
from config_handler import (
    get_initial_portfolio_settings,
    load_initial_portfolio_if_configured,
    setup_logging_from_config,
)
from helper_database import (
    DATA_DIR,
    create_transaction,
    delete_transaction,
    export_holdings_to_csv,
    export_transactions_to_csv,
    filter_transactions,
    get_all_transactions,
    get_transaction_by_id,
    init_database,
    update_transaction,
)

# =============================================================================
# Logging Setup
# =============================================================================

setup_logging_from_config(config)

logger = logging.getLogger(__name__)

logger.info("=" * 60)
logger.info("Portfolio Manager API Starting")
logger.info("=" * 60)

# Initialize database
logger.info("Initializing database...")
init_database()

# Load initial portfolio if configured
loaded_count = load_initial_portfolio_if_configured(config)
if loaded_count > 0:
    logger.info(f"Initial portfolio loaded: {loaded_count} transactions")

# Create default admin using CLI args if provided
default_username = cli_args.username or "admin"
default_password = cli_args.password or "admin"
try:
    admin = create_admin_user(username=default_username, password=default_password)
    if admin:
        if cli_args.password:
            logger.info(f"Created admin user: {default_username}")
        else:
            logger.warning(f"Created default admin user (username: {default_username}, password: {default_password}). Please change password!")
except Exception as e:
    logger.error(f"Error creating admin user: {e}")

# =============================================================================
# FastAPI App Setup
# =============================================================================

app = FastAPI(
    title="Portfolio Manager",
    description="Resource accumulation and warehouse portfolio management system with CSV persistence",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Get API config for CORS (includes env var resolution)
api_config = get_api_config(config)

# Apply CLI argument overrides (highest priority)
if cli_args.host:
    api_config['host'] = cli_args.host
    logger.info(f"Host overridden by CLI: {cli_args.host}")
if cli_args.port:
    api_config['port'] = cli_args.port
    logger.info(f"Port overridden by CLI: {cli_args.port}")
if cli_args.username:
    api_config['username'] = cli_args.username
    logger.info(f"Username set by CLI: {cli_args.username}")
if cli_args.password:
    api_config['password'] = cli_args.password
    logger.info("Password set by CLI (value hidden)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=api_config.get('cors_origins', ["*"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info(f"CORS configured with origins: {api_config.get('cors_origins', ['*'])}")


# =============================================================================
# Enums
# =============================================================================

class Direction(str, Enum):
    IN = "in"
    OUT = "out"


# =============================================================================
# Pydantic Models
# =============================================================================

class TransactionBase(BaseModel):
    """Base transaction model defining the resource movement"""
    name: str = Field(..., description="Item name (non-unique, records added time)")
    cost: float = Field(..., description="Cost per unit", ge=0)
    qty: float = Field(..., description="Quantity moved", gt=0)
    cost_units: str = Field(..., description="Unit of cost (e.g., USD, EUR, kg)")
    direction: Direction = Field(..., description="Movement direction: 'in' or 'out'")
    counterpart_id: str = Field(..., description="Source or Destination ID")
    notes: Optional[str] = Field(None, description="Optional transaction notes")


class TransactionCreate(TransactionBase):
    pass


class TransactionUpdate(BaseModel):
    """Model for updating a transaction"""
    name: Optional[str] = None
    cost: Optional[float] = Field(None, ge=0)
    qty: Optional[float] = Field(None, gt=0)
    cost_units: Optional[str] = None
    direction: Optional[Direction] = None
    counterpart_id: Optional[str] = None
    notes: Optional[str] = None


class Transaction(TransactionBase):
    """Transaction with metadata"""
    id: int = Field(..., description="Unique transaction ID")
    timestamp: datetime = Field(..., description="Transaction timestamp")
    total_value: float = Field(..., description="Calculated: cost × qty")

    class Config:
        from_attributes = True


class HoldingSummary(BaseModel):
    """Portfolio summary for a specific resource"""
    name: str
    cost_units: str
    total_in: float = Field(..., description="Total quantity received")
    total_out: float = Field(..., description="Total quantity sent")
    current_balance: float = Field(..., description="Net quantity (in - out)")
    avg_cost_in: float = Field(..., description="Average cost of incoming units")
    total_value_in: float = Field(..., description="Total value of incoming")
    total_value_out: float = Field(..., description="Total value of outgoing")


class PortfolioSummary(BaseModel):
    """Overall portfolio statistics"""
    total_transactions: int
    total_unique_items: int
    total_value_in_portfolio: float
    items: List[HoldingSummary]


class ConfigUpdate(BaseModel):
    """Model for updating configuration"""
    section: str
    key: str
    value: str


# =============================================================================
# Helper Functions
# =============================================================================

def calculate_holdings(name: Optional[str] = None) -> List[HoldingSummary]:
    """Calculate current holdings, optionally filtered by name"""
    from collections import defaultdict

    transactions = get_all_transactions()
    items_data = defaultdict(lambda: {
        "cost_units": "",
        "total_in": 0.0,
        "total_out": 0.0,
        "total_cost_in": 0.0,
        "total_value_in": 0.0,
        "total_value_out": 0.0,
    })

    for txn in transactions:
        if name and txn.get('name') != name:
            continue

        txn_name = txn.get('name', '')
        item = items_data[txn_name]
        item["cost_units"] = txn.get('cost_units', '')

        try:
            qty = float(txn.get('qty', 0))
            cost = float(txn.get('cost', 0))
        except (ValueError, TypeError):
            logger.warning(f"Invalid numeric data in transaction: {txn}")
            continue

        if txn.get('direction') == Direction.IN.value:
            item["total_in"] += qty
            item["total_cost_in"] += cost * qty
            item["total_value_in"] += cost * qty
        else:
            item["total_out"] += qty
            item["total_value_out"] += cost * qty

    holdings = []
    for item_name, data in items_data.items():
        avg_cost = data["total_cost_in"] / data["total_in"] if data["total_in"] > 0 else 0
        holdings.append(HoldingSummary(
            name=item_name,
            cost_units=data["cost_units"],
            total_in=data["total_in"],
            total_out=data["total_out"],
            current_balance=data["total_in"] - data["total_out"],
            avg_cost_in=avg_cost,
            total_value_in=data["total_value_in"],
            total_value_out=data["total_value_out"]
        ))

    return holdings


# =============================================================================
# Public Routes (No Authentication Required)
# =============================================================================

@app.get("/")
async def root():
    """Root endpoint - public"""
    return {
        "service": "Portfolio Manager API",
        "version": __version__,
        "description": "Resource accumulation and warehouse portfolio management",
        "auth_enabled": check_auth_enabled()
    }


@app.get("/health")
async def health_check():
    """Health check endpoint - public"""
    try:
        transactions_count = len(get_all_transactions())
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "transactions_count": transactions_count
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


# =============================================================================
# Authentication Routes
# =============================================================================

from fastapi.security import OAuth2PasswordRequestForm

@app.post("/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login and receive JWT token"""
    logger.info(f"Login attempt for user: {form_data.username}")
    return handle_login(form_data)


@app.post("/auth/register", response_model=User)
async def register(user_data: UserCreate):
    """Register new user"""
    logger.info(f"Registration attempt for user: {user_data.username}")
    return register_user(user_data.username, user_data.password)


@app.get("/auth/me", response_model=User)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """Get current user information"""
    return current_user


# =============================================================================
# Protected Routes (Authentication Required)
# =============================================================================

@app.post("/transactions", response_model=Transaction, status_code=status.HTTP_201_CREATED)
async def create_transaction_endpoint(
    txn: TransactionCreate,
    current_user: User = Depends(get_current_active_user)
):
    """Record a resource movement (in or out)"""
    logger.info(f"User '{current_user.username}' creating transaction: {txn.name} {txn.direction}")

    try:
        new_transaction = create_transaction(txn.model_dump())
        logger.info(f"Transaction created with ID: {new_transaction['id']}")
        return Transaction(**new_transaction)
    except Exception as e:
        logger.error(f"Error creating transaction: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create transaction: {str(e)}"
        )


@app.get("/transactions", response_model=List[Transaction])
async def get_transactions(
    name: Optional[str] = None,
    direction: Optional[Direction] = None,
    counterpart_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user)
):
    """Get transaction history with optional filtering"""
    logger.debug(f"User '{current_user.username}' fetching transactions")

    try:
        transactions = filter_transactions(
            name=name,
            direction=direction.value if direction else None,
            counterpart_id=counterpart_id,
            limit=limit,
            offset=offset
        )
        return [Transaction(**t) for t in transactions]
    except Exception as e:
        logger.error(f"Error fetching transactions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch transactions: {str(e)}"
        )


@app.get("/transactions/{transaction_id}", response_model=Transaction)
async def get_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific transaction by ID"""
    logger.debug(f"User '{current_user.username}' fetching transaction {transaction_id}")

    txn = get_transaction_by_id(transaction_id)
    if txn is None:
        logger.warning(f"Transaction {transaction_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with id {transaction_id} not found"
        )
    return Transaction(**txn)


@app.put("/transactions/{transaction_id}", response_model=Transaction)
async def update_transaction_endpoint(
    transaction_id: int,
    txn_update: TransactionUpdate,
    current_user: User = Depends(get_current_active_user)
):
    """Update an existing transaction"""
    logger.info(f"User '{current_user.username}' updating transaction {transaction_id}")

    # Filter out None values
    updates = {k: v for k, v in txn_update.model_dump().items() if v is not None}

    if not updates:
        logger.warning("Update called with no changes")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )

    updated = update_transaction(transaction_id, updates)
    if updated is None:
        logger.warning(f"Cannot update: Transaction {transaction_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with id {transaction_id} not found"
        )

    return Transaction(**updated)


@app.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction_endpoint(
    transaction_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """Delete a transaction"""
    logger.info(f"User '{current_user.username}' deleting transaction {transaction_id}")

    success = delete_transaction(transaction_id)
    if not success:
        logger.warning(f"Cannot delete: Transaction {transaction_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with id {transaction_id} not found"
        )
    return None


# =============================================================================
# Holdings/Portfolio Routes
# =============================================================================

@app.get("/holdings", response_model=List[HoldingSummary])
async def get_holdings(
    name: Optional[str] = None,
    current_user: User = Depends(get_current_active_user)
):
    """Get current portfolio holdings summary"""
    logger.debug(f"User '{current_user.username}' fetching holdings")
    return calculate_holdings(name)


@app.get("/holdings/{item_name}", response_model=HoldingSummary)
async def get_holding(
    item_name: str,
    current_user: User = Depends(get_current_active_user)
):
    """Get holdings for a specific item"""
    logger.debug(f"User '{current_user.username}' fetching holding for {item_name}")

    holdings = calculate_holdings(item_name)
    if not holdings:
        logger.warning(f"No holdings found for item: {item_name}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No holdings found for item: {item_name}"
        )
    return holdings[0]


@app.get("/portfolio/summary", response_model=PortfolioSummary)
async def get_portfolio_summary(current_user: User = Depends(get_current_active_user)):
    """Get overall portfolio statistics"""
    logger.debug(f"User '{current_user.username}' fetching portfolio summary")

    holdings = calculate_holdings()
    total_value = 0.0

    for h in holdings:
        if h.total_in > 0:
            current_value = h.current_balance * (h.total_value_in / h.total_in)
            total_value += current_value

    return PortfolioSummary(
        total_transactions=len(get_all_transactions()),
        total_unique_items=len(holdings),
        total_value_in_portfolio=total_value,
        items=holdings
    )


@app.get("/portfolio/counterpart/{counterpart_id}/history")
async def get_counterpart_history(
    counterpart_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Get transaction history with a specific counterpart"""
    logger.debug(f"User '{current_user.username}' fetching history for counterpart {counterpart_id}")

    history = filter_transactions(counterpart_id=counterpart_id, limit=10000)

    total_in = sum(t['qty'] for t in history if t.get('direction') == Direction.IN.value)
    total_out = sum(t['qty'] for t in history if t.get('direction') == Direction.OUT.value)

    return {
        "counterpart_id": counterpart_id,
        "transaction_count": len(history),
        "total_quantity_in": total_in,
        "total_quantity_out": total_out,
        "net_flow": total_in - total_out,
        "transactions": [Transaction(**t) for t in history]
    }


# =============================================================================
# Export Routes
# =============================================================================

@app.get("/export/transactions")
async def export_transactions(
    current_user: User = Depends(get_current_active_user)
):
    """Export all transactions to CSV file"""
    logger.info(f"User '{current_user.username}' exporting transactions")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_path = DATA_DIR / f"exports" / f"transactions_{timestamp}.csv"
    export_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        export_transactions_to_csv(export_path)
        return FileResponse(
            path=export_path,
            filename=f"transactions_{timestamp}.csv",
            media_type="text/csv"
        )
    except Exception as e:
        logger.error(f"Error exporting transactions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}"
        )


@app.get("/export/holdings")
async def export_holdings(
    current_user: User = Depends(get_current_active_user)
):
    """Export holdings summary to CSV"""
    logger.info(f"User '{current_user.username}' exporting holdings")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_path = DATA_DIR / f"exports" / f"holdings_{timestamp}.csv"
    export_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        holdings = calculate_holdings()
        holdings_dicts = [h.model_dump() for h in holdings]
        export_holdings_to_csv(export_path, holdings_dicts)
        return FileResponse(
            path=export_path,
            filename=f"holdings_{timestamp}.csv",
            media_type="text/csv"
        )
    except Exception as e:
        logger.error(f"Error exporting holdings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}"
        )


# =============================================================================
# Config Routes (Admin)
# =============================================================================

@app.get("/config")
async def get_config(current_user: User = Depends(get_current_active_user)):
    """Get current configuration (sensitive values masked)"""
    cfg = load_config(DEFAULT_CONFIG_PATH)

    # Return non-sensitive config
    return {
        "database": {
            "type": cfg.get('database', 'type', fallback='csv'),
            "data_dir": cfg.get('database', 'data_dir', fallback='data'),
        },
        "auth": {
            "enabled": cfg.getboolean('auth', 'enabled', fallback=True),
            "token_expire_minutes": cfg.getint('auth', 'token_expire_minutes', fallback=30),
        },
        "initial_portfolio": {
            "enabled": cfg.getboolean('initial_portfolio', 'enabled', fallback=False),
            "auto_load_on_start": cfg.getboolean('initial_portfolio', 'auto_load_on_start', fallback=False),
        },
        "logging": {
            "level": cfg.get('logging', 'level', fallback='INFO'),
        }
    }


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    logger.info("Starting Uvicorn server...")
    uvicorn.run(
        "main:app",
        host=api_config['host'],
        port=api_config['port'],
        reload=api_config['reload'],
        reload_excludes=["data/*", "logs/*"]
    )
