# Portfolio Manager API

A resource accumulation and warehouse portfolio management system built with FastAPI, featuring CSV database persistence and JWT authentication.

## Version

**Current Version:** `0.1.2`

**Compatibility Range:** Supports portfolio-manager versions `0.1.0` to `0.2.0`

## Features

- **Transaction-based**: Records all resource movements (in/out)
- **CSV Database**: Persistent storage with automatic backups
- **JWT Authentication**: Secure login with OAuth2
- **Portfolio Tracking**: Real-time holdings calculation
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
│  data/            - CSV database files & backups              │
│  logs/            - Application logs                          │
└─────────────────────────────────────────────────────────────┘
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
curl -H "Authorization: Bearer eyJ..." \
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
| POST | `/transactions` | Yes | Record movement |
| GET | `/transactions` | Yes | List transactions |
| GET | `/transactions/{id}` | Yes | Get specific |
| PUT | `/transactions/{id}` | Yes | Update |
| DELETE | `/transactions/{id}` | Yes | Delete |

### Holdings & Portfolio
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/holdings` | Yes | All holdings |
| GET | `/holdings/{name}` | Yes | Specific item |
| GET | `/portfolio/summary` | Yes | Portfolio stats |
| GET | `/portfolio/counterpart/{id}/history` | Yes | Counterpart audit |

### Export
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/export/transactions` | Yes | Download CSV |
| GET | `/export/holdings` | Yes | Download CSV |

### System
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/` | No | Welcome info |
| GET | `/health` | No | Health check |
| GET | `/config` | Yes | View config |

## Example Usage

### Add Inventory (Incoming)
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

### Remove Inventory (Outgoing)
```bash
curl -X POST "http://localhost:8000/transactions" \
  -H "Authorization: Bearer $TOKEN" \
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
curl -H "Authorization: Bearer $TOKEN" \
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
├── transactions.csv     # Main transaction database
├── users.csv           # User credentials
├── backups/            # Automatic backups
│   ├── transactions_20250416_120000.csv
│   └── ...
└── exports/            # User exports
    ├── transactions_20250416_120000.csv
    └── holdings_20250416_120000.csv
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

## Testing

See the companion test project: `portfolio-manager-tests/`

### Version Compatibility

This commit (`0.1.2`) is tested with:
- `portfolio-manager-tests` version range: `0.1.0` to `0.2.0`

When running tests, ensure the API version matches the test expectations.

## Future Extensions

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
├── config_handler.py    # INI configuration
├── helper_database.py   # Database abstraction
├── helper_csv.py        # CSV implementation
├── __init__.py          # Version and compatibility
├── config.ini           # Configuration
├── requirements.txt     # Dependencies
├── .gitignore
└── README.md
```

## License

MIT License
