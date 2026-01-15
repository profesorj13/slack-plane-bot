import logging
import json
from typing import Dict, Any, Optional
import anthropic

from config import ANTHROPIC_API_KEY
from services.plane_service import (
    create_work_item,
    suggest_module,
    resolve_assignee,
    add_to_cycle,
    get_cycles,
    get_current_cycle,
    MODULES,
    TEAM_MEMBERS,
)

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Define tools for Claude
TOOLS = [
    {
        "name": "create_ticket",
        "description": "Crea un ticket/issue en Plane para el proyecto TUNI. Usa esta herramienta cuando el usuario pida crear un ticket, issue, o tarea.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Título conciso del ticket (máximo 100 caracteres)"
                },
                "description": {
                    "type": "string",
                    "description": "Descripción detallada del ticket basada en el contexto del hilo"
                },
                "assignee": {
                    "type": "string",
                    "description": f"Nombre del asignado. Opciones: {', '.join(TEAM_MEMBERS.keys())}. Dejar vacío si no se especifica.",
                    "enum": list(TEAM_MEMBERS.keys()) + [""]
                },
                "module": {
                    "type": "string",
                    "description": f"Módulo al que pertenece. Opciones: {', '.join(MODULES.keys())}. Dejar vacío si no se puede determinar.",
                    "enum": list(MODULES.keys()) + [""]
                },
                "priority": {
                    "type": "string",
                    "description": "Prioridad del ticket",
                    "enum": ["urgent", "high", "medium", "low", "none"],
                    "default": "none"
                }
            },
            "required": ["title", "description"]
        }
    }
]

SYSTEM_PROMPT = """Eres un asistente que ayuda a crear tickets en Plane para el proyecto TUNI (tutor adaptativo universitario).

Tu tarea es:
1. Analizar el contexto de la conversación de Slack
2. Extraer la información relevante para crear un ticket
3. Usar la herramienta create_ticket con:
   - Un título claro y conciso
   - Una descripción que capture el contexto de la conversación
   - Asignar a la persona mencionada si se indica
   - Sugerir un módulo basado en el contenido si es posible

Reglas:
- Si mencionan "asigname" o "para mí", deja el assignee vacío (se asignará al que creó el mensaje)
- Si mencionan a alguien por nombre, usa ese nombre como assignee
- Infiere el módulo del contexto usando estas pistas:
  * chat, conversación, tutor, IA, prompt → tutor_conversacional
  * actividad, ejercicio, contenido, quiz → experiencias_educativas
  * métricas, progreso, insignias → modelo_estudiante
  * video, multimedia → videos_educativos
  * perfil, amigos, social → comunidad
  * dashboard, supervisor → supervisores
  * notificación, whatsapp, email → notificacion
  * integración, api, sso → integracion
  * proceso, equipo, mejora → equipo_mejora

- La descripción debe ser útil para quien trabaje en el ticket, incluyendo contexto relevante de la conversación.
- Responde siempre en español.
"""


async def interpret_and_create_ticket(
    thread_context: str,
    user_command: str,
    requesting_user: Optional[str] = None,
    api_key: Optional[str] = None,
    requester_info: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Use Claude to interpret a Slack message and create a Plane ticket.

    Args:
        thread_context: Formatted string of the thread conversation
        user_command: The message that mentioned the bot
        requesting_user: Name of the user who triggered the command
        api_key: Plane API key to use for ticket creation
        requester_info: Dict with 'name' and 'email' for fallback attribution

    Returns:
        Dict with ticket creation result or error
    """
    user_message = f"""
Contexto del hilo de Slack:
---
{thread_context}
---

Comando del usuario: {user_command}

Usuario que solicita: {requesting_user or "Desconocido"}

Analiza el contexto y crea un ticket apropiado.
"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=[{"role": "user", "content": user_message}]
        )

        # Process tool use
        for block in response.content:
            if block.type == "tool_use" and block.name == "create_ticket":
                return await _execute_create_ticket(block.input, requesting_user, api_key, requester_info)

        # If no tool was called, return an error
        return {
            "success": False,
            "error": "No se pudo interpretar el comando para crear un ticket."
        }

    except Exception as e:
        logger.error(f"Error in LLM service: {e}")
        return {
            "success": False,
            "error": f"Error al procesar: {str(e)}"
        }


async def _execute_create_ticket(
    params: Dict[str, Any],
    requesting_user: Optional[str] = None,
    api_key: Optional[str] = None,
    requester_info: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Execute the ticket creation based on LLM parameters.

    Args:
        params: Parameters extracted by Claude
        requesting_user: Name of the requesting user (for self-assignment)
        api_key: Plane API key to use for creation
        requester_info: Dict with 'name' and 'email' for fallback attribution

    Returns:
        Dict with creation result
    """
    title = params.get("title", "")
    description = params.get("description", "")
    assignee_name = params.get("assignee", "")
    module_key = params.get("module", "")
    priority = params.get("priority", "none")

    # Resolve assignee
    assignee_id = None
    if assignee_name:
        assignee_id = resolve_assignee(assignee_name)

    # If no module specified, try to suggest one from content
    if not module_key:
        module_key = suggest_module(f"{title} {description}")

    try:
        result = await create_work_item(
            name=title,
            description=description,
            assignee_id=assignee_id,
            module_key=module_key if module_key else None,
            priority=priority,
            api_key=api_key,
            requester_info=requester_info,
        )

        # Auto-assign to current cycle/sprint
        cycle_name = None
        try:
            current_cycle = await get_current_cycle(api_key)
            if current_cycle:
                cycle_added = await add_to_cycle(result["id"], current_cycle["id"], api_key)
                if cycle_added:
                    cycle_name = current_cycle["name"]
                    logger.info(f"Ticket {result['identifier']} added to cycle: {cycle_name}")
        except Exception as cycle_error:
            logger.warning(f"Could not add to cycle: {cycle_error}")

        result["cycle"] = cycle_name

        return {
            "success": True,
            "ticket": result,
            "message": f"Ticket creado: {result['identifier']}"
        }

    except Exception as e:
        logger.error(f"Error creating ticket: {e}")
        return {
            "success": False,
            "error": f"Error al crear ticket: {str(e)}"
        }
