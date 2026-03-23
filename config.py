import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load .env if it exists
_env_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                os.environ.setdefault(key.strip(), value.strip())


def _parse_locations():
    """Parse project locations from env or use defaults."""
    raw = os.environ.get('MAX_PROJECT_LOCATIONS', '')
    if raw:
        locations = {}
        for pair in raw.split(','):
            if ':' in pair:
                name, path = pair.split(':', 1)
                locations[name.strip()] = os.path.expanduser(path.strip())
        return locations

    # Default: ~/Projects for local
    return {
        'local': os.path.expanduser('~/Projects'),
    }


class Config:
    SECRET_KEY = os.environ.get('MAX_SECRET_KEY', 'agent-86-would-you-believe')
    DB_PATH = os.path.join(BASE_DIR, 'max.db')
    CLAUDE_CLI_PATH = os.environ.get('CLAUDE_CLI_PATH', os.path.expanduser('~/.local/bin/claude'))
    PROJECT_LOCATIONS = _parse_locations()
    SOCKETIO_ASYNC_MODE = 'threading'
    DEFAULT_MODEL = 'sonnet'
    DEFAULT_PERMISSION_MODE = 'plan'


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
