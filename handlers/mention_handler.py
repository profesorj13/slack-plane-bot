import logging
import asyncio
from typing import Callable

from services.slack_service import get_thread_messages, format_thread_for_llm, get_user_info
from services.llm_service import interpret_and_create_ticket

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
    channel = event.get("channel")
    thread_ts = event.get("thread_ts", event.get("ts"))
    user_id = event.get("user")
    text = event.get("text", "")

    logger.info(f"Processing mention from {user_id}: {text[:50]}...")

    try:
        result = say(
            text="Procesando tu solicitud...",
            thread_ts=thread_ts
        )
        logger.info(f"Sent 'processing' message: {result}")
    except Exception as e:
        logger.error(f"Failed to send 'processing' message: {e}")

    # Get user info
    requester = get_user_info(client, user_id)
    user_name = requester.get("name") or "Unknown"
    user_email = requester.get("email")
    requester_info = {"name": user_name, "email": user_email}

    # Get thread context
    messages = get_thread_messages(client, channel, thread_ts)
    thread_context = format_thread_for_llm(messages)

    # Create ticket
    result = run_async(
        interpret_and_create_ticket(thread_context, text, user_name, requester_info)
    )

    # Send result
    if result.get("success"):
        ticket = result.get("ticket", {})
        response = (
            f"*Ticket creado exitosamente*\n\n"
            f"*{ticket.get('key')}*: {ticket.get('name')}\n"
            f"Ver ticket: {ticket.get('url')}"
        )

        if ticket.get("epic"):
            response += f"\nEpic: {ticket.get('epic')}"

        if ticket.get("parent_story"):
            response += f"\nHistoria padre: {ticket.get('parent_story')}"

        if ticket.get("issue_type"):
            response += f"\nTipo: {ticket.get('issue_type')}"

        try:
            result_msg = say(text=response, thread_ts=thread_ts)
            logger.info(f"Sent success response: {result_msg}")
        except Exception as e:
            logger.error(f"Failed to send success response: {e}")
    else:
        error = result.get("error", "Error desconocido")
        try:
            result_msg = say(
                text=f"No pude crear el ticket: {error}",
                thread_ts=thread_ts
            )
            logger.info(f"Sent error response: {result_msg}")
        except Exception as e:
            logger.error(f"Failed to send error response: {e}")
