import logging
from typing import Dict, Any, Optional
import anthropic

from config import ANTHROPIC_API_KEY
from services.jira_service import (
    create_issue,
    suggest_epic,
    resolve_assignee,
    resolve_reporter,
    get_active_sprint,
    search_parent_stories,
    TEAM_MEMBERS,
    PROJECTS,
    EPICS,
    ISSUE_TYPES,
)

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

TOOLS = [
    {
        "name": "create_ticket",
        "description": "Crea un ticket/issue en Jira. Usa esta herramienta cuando el usuario pida crear un ticket, issue, o tarea.",
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
                "project": {
                    "type": "string",
                    "description": "Proyecto en Jira. TUNI = tutor adaptativo, TICH = plataforma tech/cronos, ALZ = Alizia, VIA = Vigía.",
                    "enum": list(PROJECTS.keys()),
                    "default": "TUNI"
                },
                "epic": {
                    "type": "string",
                    "description": "Key del epic al que pertenece. Dejar vacío si no se puede determinar. Opciones por proyecto — TUNI: mejoras_clase, mejoras_contenido, mobile, supervisores, perfil, comunidad, analisis_conversaciones. TICH: ktlo, admin, excelencia_tecnica, pagos.",
                    "default": ""
                },
                "issue_type": {
                    "type": "string",
                    "description": "Tipo de issue. Usar 'error' para bugs, 'historia' para features, 'tarea' para tasks generales, 'subtarea' si debe ir bajo una historia padre, 'design' para diseño, 'qa' para testing.",
                    "enum": list(ISSUE_TYPES.keys()),
                    "default": "tarea"
                },
                "parent_story": {
                    "type": "string",
                    "description": "Key de la Historia padre (ej: TUNI-950) si el ticket debe ser subtarea de una historia existente. Solo usar con issue_type='subtarea'.",
                    "default": ""
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

SYSTEM_PROMPT = """Eres un asistente que ayuda a crear tickets en Jira para los proyectos del equipo.

Proyectos disponibles:
- TUNI: tutor adaptativo universitario (default)
- TICH: plataforma tech / Cronos
- ALZ: Alizia
- VIA: Vigía

Tu tarea es:
1. Analizar el contexto de la conversación de Slack
2. Extraer la información relevante para crear un ticket
3. Usar la herramienta create_ticket con los campos apropiados

Reglas para inferir proyecto:
- Si mencionan "cronos", "tich", "tech" → TICH
- Si mencionan "alizia", "alz" → ALZ
- Si mencionan "vigía", "vigia", "via" → VIA
- Por defecto → TUNI

Reglas para tipo de issue:
- Bug, error, fallo, se rompe → error
- Feature, funcionalidad nueva, historia → historia
- Task, tarea genérica → tarea
- Si debe ir bajo una historia existente → subtarea

Reglas para epic (solo TUNI y TICH tienen epics):
- TUNI: clase/aula/sesión/live → mejoras_clase, contenido/actividad/quiz → mejoras_contenido, mobile/app/celular → mobile, supervisor/dashboard → supervisores, perfil/usuario/cuenta → perfil, comunidad/social/foro → comunidad, análisis/conversación/tutor/IA/chat/prompt → analisis_conversaciones
- TICH: bug/fix/urgente/hotfix → ktlo, admin/backoffice → admin, refactor/deuda técnica/performance → excelencia_tecnica, pago/suscripción/factura → pagos

Reglas de asignación:
- Si mencionan "asigname" o "para mí", deja el assignee vacío (se asignará al que creó el mensaje)
- Si mencionan a alguien por nombre, usa ese nombre como assignee

{stories_context}

Reglas de formato para la descripción (IMPORTANTE):
- Usar markdown limpio: ## para secciones, **texto** para negritas, - para bullets
- NO usar ** dentro de bullets (ej: "- **Campo:** valor" está MAL → usar "- Campo: valor")
- Estructura recomendada para bugs:
  ## Problema
  Descripción clara del bug
  ## Pasos para reproducir
  1. Paso uno
  2. Paso dos
  ## Comportamiento esperado
  Lo que debería pasar
- Estructura recomendada para tareas/historias:
  ## Contexto
  Resumen del pedido
  ## Detalles
  - Detalle 1
  - Detalle 2
- Mantener la descripción concisa y enfocada
- No incluir secciones de "Asignación" ni "Reportado por" en la descripción (eso va en campos separados)

Responde siempre en español.
"""


async def interpret_and_create_ticket(
    thread_context: str,
    user_command: str,
    requesting_user: Optional[str] = None,
    requester_info: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    user_message = f"""
Contexto del hilo de Slack:
---
{thread_context}
---

Comando del usuario: {user_command}

Usuario que solicita: {requesting_user or "Desconocido"}

Analiza el contexto y crea un ticket apropiado.
"""

    # Build stories context for the system prompt
    stories_context = ""
    try:
        # We'll inject stories after Claude picks the epic, but provide general guidance
        stories_context = "Si identificas el epic y proyecto, considera si el ticket debería ser subtarea de una historia existente."
    except Exception:
        pass

    system = SYSTEM_PROMPT.format(stories_context=stories_context)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system,
            tools=TOOLS,
            messages=[{"role": "user", "content": user_message}]
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "create_ticket":
                return await _execute_create_ticket(block.input, requesting_user, requester_info)

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
    requester_info: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    title = params.get("title", "")
    description = params.get("description", "")
    assignee_name = params.get("assignee", "")
    project_key = params.get("project", "TUNI")
    epic_slug = params.get("epic", "")
    issue_type = params.get("issue_type", "tarea")
    parent_story = params.get("parent_story", "")
    priority = params.get("priority", "none")

    # Resolve assignee
    assignee_id = resolve_assignee(assignee_name) if assignee_name else None

    # Resolve epic key
    epic_key = None
    if epic_slug and project_key in EPICS:
        epic_key = EPICS[project_key].get(epic_slug)

    # If no epic specified, try keyword suggestion
    if not epic_key:
        suggested_slug = suggest_epic(f"{title} {description}", project_key)
        if suggested_slug and project_key in EPICS:
            epic_key = EPICS[project_key].get(suggested_slug)

    # Search parent stories if we have an epic (for subtask recommendation)
    stories = []
    if epic_key and issue_type == "subtarea" and not parent_story:
        stories = await search_parent_stories(project_key, epic_key)
        if stories:
            logger.info(f"Found {len(stories)} parent stories under {epic_key}")

    # Get active sprint for TUNI (only project with a board)
    sprint_id = None
    project_config = PROJECTS.get(project_key, {})
    board_id = project_config.get("board_id")
    if board_id:
        sprint = await get_active_sprint(board_id)
        if sprint:
            sprint_id = sprint.get("id")
            logger.info(f"Using active sprint: {sprint.get('name')}")

    # Resolve reporter from requester email
    reporter_id = None
    if requester_info and requester_info.get("email"):
        reporter_id = resolve_reporter(requester_info["email"])

    try:
        result = await create_issue(
            title=title,
            description=description,
            assignee_id=assignee_id,
            epic_key=epic_key,
            priority=priority,
            project_key=project_key,
            issue_type=issue_type,
            sprint_id=sprint_id,
            parent_key=parent_story if parent_story else None,
            requester_info=requester_info if not reporter_id else None,
            reporter_id=reporter_id,
        )

        return {
            "success": True,
            "ticket": result,
            "message": f"Ticket creado: {result['key']}"
        }

    except Exception as e:
        logger.error(f"Error creating ticket: {e}")
        return {
            "success": False,
            "error": f"Error al crear ticket: {str(e)}"
        }
