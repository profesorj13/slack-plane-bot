import os
from dotenv import load_dotenv

load_dotenv()

# Slack
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")

# Anthropic
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# Plane
PLANE_API_KEY = os.environ.get("PLANE_API_KEY")  # Default/fallback API key
PLANE_BASE_URL = os.environ.get("PLANE_BASE_URL", "https://api.plane.so/api/v1")
PLANE_WORKSPACE_SLUG = os.environ.get("PLANE_WORKSPACE_SLUG")
PLANE_DEFAULT_PROJECT_ID = os.environ.get("PLANE_DEFAULT_PROJECT_ID", "bb12a857-553e-414d-9b4c-d59225c93a4f")  # TUNI

# Mapeo de emails de Slack a API Keys personales de Plane
# Cada usuario debe generar su API Key en Plane: Profile Settings > Personal Access Tokens
PLANE_USER_API_KEYS = {
    "juan.mateos@educabot.com": os.environ.get("PLANE_API_KEY_JUAN"),
    "rocio.etchebarne@educabot.com": os.environ.get("PLANE_API_KEY_ROCIO"),
    "francisco.conte@educabot.com": os.environ.get("PLANE_API_KEY_FRANCISCO"),
    "alejo.bonadeo@educabot.com": os.environ.get("PLANE_API_KEY_ALEJO"),
    "leonardo.cano@educabot.com": os.environ.get("PLANE_API_KEY_LEONARDO"),
    "pablo.dallago@educabot.com": os.environ.get("PLANE_API_KEY_PABLO"),
    "leonardo.monzon@educabot.com": os.environ.get("PLANE_API_KEY_LMONZON"),
    "jose.attento@educabot.com": os.environ.get("PLANE_API_KEY_JOSE"),
}
