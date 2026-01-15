import logging
import asyncio
from typing import Callable

from services.slack_service import get_thread_messages, format_thread_for_llm, get_user_info
from services.llm_service import interpret_and_create_ticket
from config import PLANE_USER_API_KEYS, PLANE_API_KEY

logger = logging.getLogger(__name__)


def run_async(coro):
    """Run async coroutine in a sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def handle_mention(event: dict, say: Callable, client) -> None:
    """
    Handle when the bot is mentioned in Slack.

    Args:
        event: Slack event data
        say: Function to send messages
        client: Slack WebClient
    """
    channel = event.get("channel")
    thread_ts = event.get("thread_ts", event.get("ts"))
    user_id = event.get("user")
    text = event.get("text", "")

    logger.info(f"Processing mention from {user_id}: {text[:50]}...")

    # Acknowledge receipt
    say(
        text="Procesando tu solicitud...",
        thread_ts=thread_ts
    )

    # Get user info (name and email)
    requester = get_user_info(client, user_id)
    user_name = requester.get("name") or "Unknown"
    user_email = requester.get("email")

    # Resolve API key for this user
    user_api_key = None
    requester_info = None  # Only set if using fallback

    if user_email:
        # Get API key for this user (may be None if env var not set)
        user_api_key = PLANE_USER_API_KEYS.get(user_email)

    # If no valid user API key, use fallback and add requester note
    if not user_api_key:
        user_api_key = PLANE_API_KEY if PLANE_API_KEY else None
        requester_info = {"name": user_name, "email": user_email}
        logger.info(f"No API key configured for {user_email}, using default with requester note")

    # Get thread context
    messages = get_thread_messages(client, channel, thread_ts)
    thread_context = format_thread_for_llm(messages)

    # Run async operation
    result = run_async(
        interpret_and_create_ticket(thread_context, text, user_name, user_api_key, requester_info)
    )

    # Send result
    if result.get("success"):
        ticket = result.get("ticket", {})
        response = (
            f"*Ticket creado exitosamente*\n\n"
            f"*{ticket.get('identifier')}*: {ticket.get('name')}\n"
            f"Ver ticket: {ticket.get('url')}"
        )

        if ticket.get("module"):
            response += f"\nMódulo: {ticket.get('module')}"

        if ticket.get("cycle"):
            response += f"\nSprint: {ticket.get('cycle')}"

        say(text=response, thread_ts=thread_ts)
    else:
        error = result.get("error", "Error desconocido")
        say(
            text=f"No pude crear el ticket: {error}",
            thread_ts=thread_ts
        )
