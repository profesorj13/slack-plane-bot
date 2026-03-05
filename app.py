import os
import logging
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from config import SLACK_BOT_TOKEN, SLACK_APP_TOKEN
from handlers.mention_handler import handle_mention

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the Slack app
app = App(token=SLACK_BOT_TOKEN, logger=logger)


@app.middleware
def log_all_events(body, next):
    """Log every incoming event for debugging."""
    event_type = body.get("event", {}).get("type", "unknown")
    logger.info(f">>> Incoming event: {event_type} | keys: {list(body.keys())}")
    next()


@app.event("app_mention")
def on_app_mention(event, say, client):
    """Handle when the bot is mentioned in a channel or thread."""
    logger.info(f"Received mention from user {event.get('user')} in channel {event.get('channel')}")
    handle_mention(event, say, client)


@app.event("message")
def handle_message_events(body, logger):
    """Handle direct messages to the bot."""
    pass


@app.error
def global_error_handler(error, body, logger):
    """Global error handler for the app."""
    logger.exception(f"Error: {error}")
    logger.info(f"Request body: {body}")


if __name__ == "__main__":
    from config import JIRA_EMAIL, JIRA_API_TOKEN
    token_preview = f"{JIRA_API_TOKEN[:8]}...{JIRA_API_TOKEN[-8:]}" if JIRA_API_TOKEN and len(JIRA_API_TOKEN) > 16 else "NOT SET"
    logger.info(f"Starting Jira Bot... (email={JIRA_EMAIL}, token={token_preview}, len={len(JIRA_API_TOKEN) if JIRA_API_TOKEN else 0})")
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
