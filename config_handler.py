"""
Configuration Handler - Portfolio Manager

Manages INI file configuration including:
- Initial portfolio settings
- CSV import paths
- Database settings
- Logging configuration
"""
import configparser
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path("config.ini")


def get_default_config() -> configparser.ConfigParser:
    """Generate default configuration"""
    config = configparser.ConfigParser()

    # General settings
    config['DEFAULT'] = {
        'app_name': 'Portfolio Manager',
        'version': '1.0.0',
        'debug': 'false'
    }

    # Database settings
    config['database'] = {
        'type': 'csv',  # Options: csv, sqlite, postgresql
        'data_dir': 'data',
        'auto_backup': 'true',
        'backup_count': '10'
    }

    # Initial portfolio settings
    config['initial_portfolio'] = {
        'enabled': 'false',
        'transactions_csv': '',  # Path to initial transactions CSV
        'auto_load_on_start': 'false',
        'clear_existing_on_load': 'false'
    }

    # Authentication settings
    config['auth'] = {
        'enabled': 'true',
        'token_expire_minutes': '30',
        'secret_key': 'change-me-in-production',
        'algorithm': 'HS256'
    }

    # API settings
    config['api'] = {
        'host': '0.0.0.0',
        'port': '8000',
        'reload': 'true',
        'cors_origins': '*'
    }

    # Logging settings
    config['logging'] = {
        'level': 'INFO',  # DEBUG, INFO, WARNING, ERROR, CRITICAL
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'file': 'logs/portfolio_manager.log',
        'max_bytes': '10485760',  # 10MB
        'backup_count': '5'
    }

    return config


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> configparser.ConfigParser:
    """Load configuration from INI file, create default if not exists"""
    config = get_default_config()

    if config_path.exists():
        try:
            config.read(config_path)
            logger.info(f"Loaded configuration from {config_path}")
        except Exception as e:
            logger.error(f"Error loading config from {config_path}: {e}. Using defaults.")
    else:
        # Create default config file
        save_config(config, config_path)
        logger.info(f"Created default configuration at {config_path}")

    return config


def save_config(config: configparser.ConfigParser, config_path: Path = DEFAULT_CONFIG_PATH):
    """Save configuration to INI file"""
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            config.write(f)
        logger.debug(f"Saved configuration to {config_path}")
    except Exception as e:
        logger.error(f"Error saving config to {config_path}: {e}")
        raise


def setup_logging_from_config(config: configparser.ConfigParser):
    """Configure Python logging from config settings"""
    log_config = config['logging']

    level_name = log_config.get('level', 'INFO').upper()
    level = getattr(logging, level_name, logging.INFO)

    log_format = log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Ensure log directory exists
    log_file = log_config.get('file', 'logs/portfolio_manager.log')
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

    handlers = [logging.StreamHandler()]

    if log_file:
        try:
            from logging.handlers import RotatingFileHandler
            max_bytes = log_config.getint('max_bytes', 10485760)
            backup_count = log_config.getint('backup_count', 5)
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count
            )
            handlers.append(file_handler)
            logger.info(f"Logging to file: {log_file}")
        except Exception as e:
            logger.warning(f"Could not set up file logging: {e}")

    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=handlers,
        force=True  # Python 3.8+
    )

    logger.info(f"Logging configured at level: {level_name}")


def get_initial_portfolio_settings(config: configparser.ConfigParser) -> Dict[str, Any]:
    """Get initial portfolio configuration"""
    section = config['initial_portfolio']
    return {
        'enabled': section.getboolean('enabled', False),
        'transactions_csv': section.get('transactions_csv', ''),
        'auto_load_on_start': section.getboolean('auto_load_on_start', False),
        'clear_existing_on_load': section.getboolean('clear_existing_on_load', False)
    }


def load_initial_portfolio_if_configured(config: configparser.ConfigParser) -> int:
    """Load initial portfolio from CSV if configured"""
    from helper_database import load_initial_transactions_from_csv

    settings = get_initial_portfolio_settings(config)

    if not settings['enabled']:
        logger.info("Initial portfolio loading is disabled")
        return 0

    csv_path = Path(settings['transactions_csv'])
    if not csv_path.exists():
        logger.error(f"Initial portfolio CSV not found: {csv_path}")
        return 0

    try:
        count = load_initial_transactions_from_csv(
            csv_path,
            append=not settings['clear_existing_on_load']
        )
        logger.info(f"Loaded {count} transactions from initial portfolio CSV")
        return count
    except Exception as e:
        logger.error(f"Failed to load initial portfolio: {e}")
        return 0


def update_config_value(
    config: configparser.ConfigParser,
    section: str,
    key: str,
    value: Any,
    config_path: Path = DEFAULT_CONFIG_PATH
):
    """Update a specific config value and save"""
    if section not in config:
        config[section] = {}

    config[section][key] = str(value)
    save_config(config, config_path)
    logger.info(f"Updated config [{section}].{key} = {value}")


def get_database_config(config: configparser.ConfigParser) -> Dict[str, Any]:
    """Get database configuration"""
    section = config['database']
    return {
        'type': section.get('type', 'csv'),
        'data_dir': section.get('data_dir', 'data'),
        'auto_backup': section.getboolean('auto_backup', True),
        'backup_count': section.getint('backup_count', 10)
    }


def get_auth_config(config: configparser.ConfigParser) -> Dict[str, Any]:
    """Get authentication configuration"""
    section = config['auth']
    return {
        'enabled': section.getboolean('enabled', True),
        'token_expire_minutes': section.getint('token_expire_minutes', 30),
        'secret_key': section.get('secret_key', 'change-me-in-production'),
        'algorithm': section.get('algorithm', 'HS256')
    }


def get_api_config(config: configparser.ConfigParser) -> Dict[str, Any]:
    """Get API server configuration"""
    section = config['api']
    return {
        'host': section.get('host', '0.0.0.0'),
        'port': section.getint('port', 8000),
        'reload': section.getboolean('reload', True),
        'cors_origins': section.get('cors_origins', '*').split(',')
    }
