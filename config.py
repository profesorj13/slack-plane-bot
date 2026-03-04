import os
from dotenv import load_dotenv

load_dotenv()

# Slack
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")

# Anthropic
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# Jira
JIRA_EMAIL = os.environ.get("JIRA_EMAIL")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN")
JIRA_CLOUD_ID = os.environ.get("JIRA_CLOUD_ID", "b171db1b-26f3-4903-98d1-0dcfca599382")
JIRA_SITE_URL = os.environ.get("JIRA_SITE_URL", "https://aula-educabot.atlassian.net")
