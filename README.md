# Portfolio Manager API

A resource accumulation and warehouse portfolio management system built with FastAPI, featuring CSV database persistence, JWT authentication, and **multi-portfolio support**.

## Version

**Current Version:** `0.2.0`

**Compatibility Range:** Supports portfolio-manager versions `0.2.0` to `0.3.0`

## Features

- **Transaction-based**: Records all resource movements (in/out)
- **CSV Database**: Persistent storage with automatic backups
- **JWT Authentication**: Secure login with OAuth2
- **Portfolio Tracking**: Real-time holdings calculation
- **Multi-Portfolio Support**: Separate portfolios with access control
- **Initial Portfolio Loading**: Load starting data from CSV
- **Comprehensive Logging**: Full audit trail of decisions and errors
- **Modular Architecture**: Easy to switch from CSV to real database
- **Flexible Configuration**: CLI args, env vars, or config file

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Portfolio Manager API                    │
├─────────────────────────────────────────────────────────────┤
│  main.py          - FastAPI application & endpoints         │
│  auth.py          - JWT authentication module               │
│  config_handler.py - INI configuration management           │
├─────────────────────────────────────────────────────────────┤
│  helper_database.py - Abstraction layer                     │
│  helper_csv.py    - CSV database implementation             │
│  (helper_db.py)   - Future: SQL database implementation     │
├─────────────────────────────────────────────────────────────┤
│  config.ini       - Application configuration               │
│  data/            - CSV database files & backups            │
│   ├── {portfolio}/transactions.csv  - Per-portfolio data  │
│   ├── users.csv                       - Shared users        │
│   └── backups/                        - Auto backups         │
│  logs/            - Application logs                          │
└─────────────────────────────────────────────────────────────┘
```

## Multi-Portfolio Support

The API supports multiple isolated portfolios. Each portfolio has its own data directory and transactions.

### Portfolio Access Control

Access is configured in `config.ini` `[portfolios]` section:

```ini
[portfolios]
# Format: portfolio_name = comma-separated list of allowed users
# Admin has access to all portfolios automatically
# Empty portfolio name "" is the default portfolio

# Default portfolio (empty name) - accessible by admin and testuser
default = admin, testuser

# Custom portfolios
warehouse = admin, manager, operator
sales = admin, sales1, sales2
accounting = admin, accountant
```

**Access Rules:**
1. **Admin** has access to **all portfolios**
2. Each **user** automatically has access to their **own portfolio** (named after username)
3. Additional portfolios configured in `[portfolios]` section

### Using Portfolios

Pass the portfolio name via the `X-Portfolio` header:

```bash
# Access default portfolio (no header needed)
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/holdings"

# Access specific portfolio
curl -H "Authorization: Bearer $TOKEN" \
  -H "X-Portfolio: warehouse" \
  "http://localhost:8000/holdings"

# Create transaction in specific portfolio
curl -X POST "http://localhost:8000/transactions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Portfolio: warehouse" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Steel Bars",
    "cost": 45.50,
    "qty": 100,
    "cost_units": "USD",
    "direction": "in",
    "counterpart_id": "SUPPLIER_001"
  }'
```

### Data Structure

Each portfolio is isolated in its own directory:

```
data/
├── users.csv                    # Shared user database
├── transactions.csv             # Default portfolio (empty name)
├── backups/                     # Default portfolio backups
│   └── transactions_20250420_120000.csv
│
├── warehouse/                   # "warehouse" portfolio
│   ├── transactions.csv
│   └── backups/
│       └── transactions_20250420_120000.csv
│
├── sales/                       # "sales" portfolio
│   ├── transactions.csv
│   └── backups/
│       └── transactions_20250420_120000.csv
│
└── exports/                     # Export files
    ├── transactions_warehouse_20250420_120000.csv
    ├── holdings_warehouse_20250420_120000.csv
    └── ...
```

## Configuration Priority

Configuration values are loaded in this priority (highest to lowest):

1. **Command line arguments** (`--host`, `--port`, `--user`, `--password`)
2. **Environment variables** (`PORTFOLIO_MANAGER_HOST`, `PORTFOLIO_MANAGER_PORT`, etc.)
3. **Config file** (`config.ini`)
4. **Default values**

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORTFOLIO_MANAGER_HOST` | Server bind address | `0.0.0.0` |
| `PORTFOLIO_MANAGER_PORT` | Server port | `8000` |
| `PORTFOLIO_MANAGER_USER` | Default admin username | (none) |
| `PORTFOLIO_MANAGER_PASSWORD` | Default admin password | (none) |

### Command Line Arguments

```bash
python main.py --help
```

Options:
- `--host HOST` - Server host (overrides config)
- `--port PORT` - Server port (overrides config)
- `--user USERNAME` - Default admin username
- `--password PASSWORD` - Default admin password
- `--version` - Show version and compatibility range

Examples:
```bash
# Show version
python main.py --version

# Run on custom host/port
python main.py --host 127.0.0.1 --port 9000

# Set default credentials
python main.py --user admin --password secret123

# Via environment variables
PORTFOLIO_MANAGER_HOST=0.0.0.0 PORTFOLIO_MANAGER_PORT=8080 python main.py
```

## Data Model

### Transaction
| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Auto-assigned unique ID |
| `timestamp` | datetime | Transaction time (auto-set) |
| `name` | string | Item name (non-unique) |
| `cost` | float | Cost per unit |
| `qty` | float | Quantity moved |
| `cost_units` | string | Currency/unit type |
| `direction` | enum | "in" or "out" |
| `counterpart_id` | string | Source/Destination ID |
| `notes` | string | Optional notes |
| `total_value` | float | Calculated: cost × qty |

## Quick Start

### 1. Setup Virtual Environment

```bash
cd portfolio-manager
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### 2. Configure Application

```bash
# Edit config.ini for your needs
# Key settings:
# - auth.secret_key: Change this in production!
# - initial_portfolio: Configure initial CSV loading
# - portfolios: Configure multi-portfolio access control
# - logging.level: Set to DEBUG for troubleshooting
```

### 3. Run the Server

```bash
# Default (uses config.ini)
python main.py

# With custom host/port
python main.py --host 127.0.0.1 --port 9000

# With environment variables
PORTFOLIO_MANAGER_PORT=8080 python main.py
```

Server starts at `http://localhost:8000` (or your configured host/port)

### 4. Access Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Authentication

### Login
```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin" \
  -d "password=admin"
```

Response:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Using the Token
Include in requests:
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/holdings"
```

### Register New User
```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username": "newuser", "password": "secret123"}'
```

## API Endpoints

### Authentication
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/login` | No | Login, get JWT token |
| POST | `/auth/register` | No | Register new user |
| GET | `/auth/me` | Yes | Get current user info |

### Transactions
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/transactions` | Yes | Record movement (in portfolio) |
| GET | `/transactions` | Yes | List transactions (from portfolio) |
| GET | `/transactions/{id}` | Yes | Get specific (from portfolio) |
| PUT | `/transactions/{id}` | Yes | Update (in portfolio) |
| DELETE | `/transactions/{id}` | Yes | Delete (from portfolio) |

### Holdings & Portfolio
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/holdings` | Yes | All holdings (from portfolio) |
| GET | `/holdings/{name}` | Yes | Specific item (from portfolio) |
| GET | `/portfolio/summary` | Yes | Portfolio stats |
| GET | `/portfolio/counterpart/{id}/history` | Yes | Counterpart audit |

### Export
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/export/transactions` | Yes | Download CSV (from portfolio) |
| GET | `/export/holdings` | Yes | Download CSV (from portfolio) |

### System
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/` | No | Welcome info |
| GET | `/health` | No | Health check |
| GET | `/config` | Yes | View config |

**Note:** All protected endpoints accept an optional `X-Portfolio` header to specify the portfolio. If omitted, the default portfolio is used.

## Example Usage

### Add Inventory (Incoming) to Default Portfolio
```bash
curl -X POST "http://localhost:8000/transactions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Steel Bars",
    "cost": 45.50,
    "qty": 100,
    "cost_units": "USD",
    "direction": "in",
    "counterpart_id": "SUPPLIER_001",
    "notes": "Initial stock"
  }'
```

### Add Inventory to Specific Portfolio
```bash
curl -X POST "http://localhost:8000/transactions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Portfolio: warehouse" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Steel Bars",
    "cost": 45.50,
    "qty": 100,
    "cost_units": "USD",
    "direction": "in",
    "counterpart_id": "SUPPLIER_001",
    "notes": "Warehouse stock"
  }'
```

### Remove Inventory (Outgoing)
```bash
curl -X POST "http://localhost:8000/transactions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Portfolio: warehouse" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Steel Bars",
    "cost": 45.50,
    "qty": 20,
    "cost_units": "USD",
    "direction": "out",
    "counterpart_id": "CUSTOMER_ACME",
    "notes": "Sale to ACME Corp"
  }'
```

### Check Holdings
```bash
# Default portfolio
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/holdings"

# Specific portfolio
curl -H "Authorization: Bearer $TOKEN" \
  -H "X-Portfolio: warehouse" \
  "http://localhost:8000/holdings"
```

Response:
```json
[
  {
    "name": "Steel Bars",
    "cost_units": "USD",
    "total_in": 100,
    "total_out": 20,
    "current_balance": 80,
    "avg_cost_in": 45.50,
    "total_value_in": 4550.00,
    "total_value_out": 910.00
  }
]
```

## Initial Portfolio Loading

Configure `config.ini`:

```ini
[initial_portfolio]
enabled = true
transactions_csv = data/initial_portfolio.csv
auto_load_on_start = true
clear_existing_on_load = false
```

Create `data/initial_portfolio.csv`:
```csv
name,cost,qty,cost_units,direction,counterpart_id,notes
Steel Bars,45.50,100,USD,in,SUPPLIER_001,Opening balance
Copper Wire,12.30,500,USD,in,SUPPLIER_002,Opening balance
```

**Note:** Initial portfolio loading only loads into the default portfolio. For multi-portfolio setup, use the API endpoints after startup.

## Database Architecture

### Controlled Interface Pattern

The `helper_database.py` module acts as an abstraction layer:

```python
# Currently imports from helper_csv
from helper_csv import *

# To switch to SQL database, change to:
# from helper_db import *
```

This allows transparent switching without changing API code.

### CSV Storage Structure

```
data/
├── users.csv                    # Shared user database
├── transactions.csv             # Default portfolio
├── backups/                   # Default portfolio backups
│   └── transactions_20250420_120000.csv
│
├── {portfolio}/               # Per-portfolio directories
│   ├── transactions.csv
│   └── backups/
│       └── transactions_20250420_120000.csv
│
└── exports/                   # User exports
    ├── transactions_{portfolio}_{timestamp}.csv
    └── holdings_{portfolio}_{timestamp}.csv
```

## Logging

Logs are written to:
- Console (always)
- `logs/portfolio_manager.log` (file rotation enabled)

Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

Configure in `config.ini`:
```ini
[logging]
level = INFO
file = logs/portfolio_manager.log
```

## Security Notes

1. **Change the default secret key** in production:
   ```ini
   [auth]
   secret_key = your-256-bit-secret-key-here
   ```

2. **Change the default admin password** immediately after first login

3. **Use HTTPS** in production (configure reverse proxy)

4. **Review CORS settings** for production:
   ```ini
   [api]
   cors_origins = https://yourdomain.com
   ```

5. **Review portfolio access** - admin has access to all portfolios

## Testing

See the companion test project: `portfolio-manager-tests/`

### Version Compatibility

This commit (`0.2.0`) is tested with:
- `portfolio-manager-tests` version `0.1.0`
- **All 37 tests passed**

When running tests, ensure the API version matches the test expectations.

## Future Extensions

- [x] Multi-portfolio support with access control
- [ ] SQLite/PostgreSQL database backend (`helper_db.py`)
- [ ] User roles and permissions
- [ ] Transaction batch imports
- [ ] Reporting endpoints with charts
- [ ] Webhook notifications
- [ ] Database migrations

## Project Structure

```
portfolio-manager/
├── main.py              # FastAPI application
├── auth.py              # JWT authentication
├── config_handler.py    # INI configuration (portfolio access control)
├── helper_database.py   # Database abstraction
├── helper_csv.py        # CSV implementation (per-portfolio storage)
├── __init__.py          # Version and compatibility
├── config.ini           # Configuration
├── requirements.txt     # Dependencies
├── .gitignore
└── README.md
```

## License

MIT License
