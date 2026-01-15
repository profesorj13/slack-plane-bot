import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def get_thread_messages(client, channel: str, thread_ts: str) -> List[Dict[str, Any]]:
    """
    Retrieve all messages from a thread.

    Args:
        client: Slack WebClient instance
        channel: Channel ID where the thread is located
        thread_ts: Timestamp of the parent message (thread)

    Returns:
        List of message dictionaries with user info resolved
    """
    try:
        result = client.conversations_replies(
            channel=channel,
            ts=thread_ts,
            limit=100
        )

        messages = result.get("messages", [])

        # Resolve user names for better context
        resolved_messages = []
        user_cache = {}

        for msg in messages:
            user_id = msg.get("user")

            # Get user name from cache or API
            if user_id and user_id not in user_cache:
                try:
                    user_info = client.users_info(user=user_id)
                    user_cache[user_id] = user_info["user"]["real_name"] or user_info["user"]["name"]
                except Exception:
                    user_cache[user_id] = user_id

            resolved_messages.append({
                "user": user_cache.get(user_id, "Unknown"),
                "user_id": user_id,
                "text": msg.get("text", ""),
                "ts": msg.get("ts")
            })

        return resolved_messages

    except Exception as e:
        logger.error(f"Error fetching thread messages: {e}")
        return []


def format_thread_for_llm(messages: List[Dict[str, Any]]) -> str:
    """
    Format thread messages into a readable string for the LLM.

    Args:
        messages: List of message dictionaries

    Returns:
        Formatted string representation of the conversation
    """
    if not messages:
        return "No hay mensajes en el hilo."

    formatted = []
    for msg in messages:
        # Skip bot mentions (the command itself)
        if "<@" in msg.get("text", "") and "crea" in msg.get("text", "").lower():
            continue
        formatted.append(f"**{msg['user']}**: {msg['text']}")

    return "\n".join(formatted)


def get_user_email(client, user_id: str) -> Optional[str]:
    """
    Get the email address of a Slack user.

    Args:
        client: Slack WebClient instance
        user_id: Slack user ID

    Returns:
        User's email address or None if not available
    """
    try:
        user_info = client.users_info(user=user_id)
        return user_info["user"]["profile"].get("email")
    except Exception as e:
        logger.error(f"Error getting user email for {user_id}: {e}")
        return None


def get_user_info(client, user_id: str) -> Dict[str, Optional[str]]:
    """
    Get name and email of a Slack user.

    Args:
        client: Slack WebClient instance
        user_id: Slack user ID

    Returns:
        Dict with 'name' and 'email' keys
    """
    try:
        user_info = client.users_info(user=user_id)
        user = user_info["user"]
        return {
            "name": user.get("real_name") or user.get("name"),
            "email": user["profile"].get("email")
        }
    except Exception as e:
        logger.error(f"Error getting user info for {user_id}: {e}")
        return {"name": None, "email": None}


def extract_mentioned_users(client, text: str) -> List[Dict[str, str]]:
    """
    Extract user IDs mentioned in a message and resolve their names.

    Args:
        client: Slack WebClient instance
        text: Message text that may contain user mentions

    Returns:
        List of dicts with user_id and name
    """
    import re

    mentions = re.findall(r'<@([A-Z0-9]+)>', text)
    users = []

    for user_id in mentions:
        try:
            user_info = client.users_info(user=user_id)
            users.append({
                "user_id": user_id,
                "name": user_info["user"]["real_name"] or user_info["user"]["name"]
            })
        except Exception:
            users.append({"user_id": user_id, "name": user_id})

    return users
