import logging
import httpx
from typing import Optional, List, Dict, Any

from config import PLANE_API_KEY, PLANE_BASE_URL, PLANE_WORKSPACE_SLUG, PLANE_DEFAULT_PROJECT_ID

logger = logging.getLogger(__name__)

# =============================================================================
# CACHED IDS - Evita llamadas innecesarias al API
# =============================================================================

PROJECT_CONFIG = {
    "project_id": "bb12a857-553e-414d-9b4c-d59225c93a4f",
    "project_key": "TUNI",
    "workspace_slug": PLANE_WORKSPACE_SLUG or "aliziai",
}

TEAM_MEMBERS = {
    "juan": "e130b9b1-16fb-4d98-9012-0bc8209af43e",
    "rocio": "91bfac58-d45d-47ac-b6d6-b47ce8cb29e8",
    "francisco": "7c24e3ee-e437-41c6-a128-e6a6a0ac4f14",
    "alejo": "b715db4a-f5b4-45f6-a6c2-be100a9ef9df",
    "leonardo": "67f86a76-15cc-4b5e-b218-94bd03d770b1",
    "pablo": "7965d186-1302-4dca-bfcb-67f6abf6275b",
}

MODULES = {
    "tutor_conversacional": "2e1c1b99-df79-4c76-a347-5437b1fd48ca",
    "experiencias_educativas": "96274ea5-8502-4432-8233-839836b7a409",
    "modelo_estudiante": "5b431e9d-b740-47dc-9ce9-ed3369ca758b",
    "videos_educativos": "f7e2f0ae-82b2-4a62-bd42-4c53b7989a87",
    "comunidad": "8a24732b-8e70-47d4-a3a6-ae1ca261b152",
    "supervisores": "1f7c75e8-73c0-488a-a6dc-11c2d34c70a1",
    "notificacion": "24695d3b-ab5a-4219-ae34-62202f0c829c",
    "integracion": "a2174411-2770-4b2a-8c1a-b264889bfc26",
    "equipo_mejora": "4baa7c7c-d3d4-4feb-b373-8c3aea709816",
}

# Estados del proyecto
STATES = {
    "backlog": "42fc9f02-8a9c-430f-8aa5-4c1e64c52ce1",
    "todo": "a36a189e-b422-4836-88aa-417639c85bc6",
    "in_progress": "a1a037f7-2d7f-4619-9dda-53573c5d7305",
    "done": "cc64549c-2f25-4b12-88b9-5ab42bf63644",
    "en_revision": "83c0178c-6cb1-44e4-9cb1-14237e4b73ed",
    "cancelled": "8de742d9-529b-4d7d-901a-f2a3a3417ebf",
    "qa": "9df7d88c-2103-4946-ad6d-66395dc5fb7e",
}

DEFAULT_STATE = STATES["todo"]  # Por default, los tickets se crean en "Todo"

# Keywords para sugerir módulos automáticamente
MODULE_KEYWORDS = {
    "tutor_conversacional": ["chat", "conversación", "tutor", "ia", "prompt", "llm", "claude"],
    "experiencias_educativas": ["actividad", "ejercicio", "contenido", "quiz", "experiencia", "lección"],
    "modelo_estudiante": ["métricas", "progreso", "insignias", "dominio", "estudiante", "perfil"],
    "videos_educativos": ["video", "multimedia", "grabación"],
    "comunidad": ["perfil", "amigos", "social", "comunidad"],
    "supervisores": ["dashboard", "supervisor", "autoridad", "admin"],
    "notificacion": ["notificación", "whatsapp", "email", "mensaje"],
    "integracion": ["integración", "api", "sso", "webhook"],
    "equipo_mejora": ["proceso", "equipo", "mejora", "retro"],
}


def get_headers(api_key: Optional[str] = None) -> Dict[str, str]:
    """
    Get authorization headers for Plane API.

    Args:
        api_key: Optional API key to use. If not provided, uses the default PLANE_API_KEY.

    Raises:
        ValueError: If no valid API key is available.
    """
    # Use provided key if valid, otherwise fall back to default
    key = api_key if api_key else PLANE_API_KEY

    if not key:
        raise ValueError("No valid Plane API key configured. Please set PLANE_API_KEY environment variable.")

    return {
        "X-API-Key": key,
        "Content-Type": "application/json",
    }


def suggest_module(text: str) -> Optional[str]:
    """
    Suggest a module based on keywords in the text.

    Args:
        text: Text to analyze for keywords

    Returns:
        Module key if a match is found, None otherwise
    """
    text_lower = text.lower()

    for module_key, keywords in MODULE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                return module_key

    return None


def resolve_assignee(name: str) -> Optional[str]:
    """
    Resolve an assignee name to their ID.

    Args:
        name: Name of the team member (partial match supported)

    Returns:
        User ID if found, None otherwise
    """
    name_lower = name.lower().strip()

    for member_name, member_id in TEAM_MEMBERS.items():
        if member_name in name_lower or name_lower in member_name:
            return member_id

    return None


async def create_work_item(
    name: str,
    description: str = "",
    assignee_id: Optional[str] = None,
    module_key: Optional[str] = None,
    priority: str = "none",
    api_key: Optional[str] = None,
    requester_info: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Create a new work item (ticket) in Plane.

    Args:
        name: Title of the work item
        description: Description in HTML format
        assignee_id: UUID of the assignee (use resolve_assignee to get this)
        module_key: Key from MODULES dict to assign to a module
        priority: Priority level (urgent, high, medium, low, none)
        api_key: API key to use for creation (determines created_by)
        requester_info: Dict with 'name' and 'email' of the requester (for fallback note)

    Returns:
        Dict with created work item info including URL
    """
    workspace = PROJECT_CONFIG["workspace_slug"]
    project_id = PROJECT_CONFIG["project_id"]

    url = f"{PLANE_BASE_URL}/workspaces/{workspace}/projects/{project_id}/issues/"

    # Build description - add requester note if using fallback API key
    final_description = description
    if requester_info and requester_info.get("name"):
        requester_note = f"<p><em>Solicitado por: {requester_info['name']}"
        if requester_info.get("email"):
            requester_note += f" ({requester_info['email']})"
        requester_note += "</em></p><hr>"
        final_description = requester_note + (f"<p>{description}</p>" if description else "")
    else:
        final_description = f"<p>{description}</p>" if description else ""

    payload = {
        "name": name,
        "description_html": final_description,
        "priority": priority,
        "state": DEFAULT_STATE,  # Por default en "Todo"
    }

    if assignee_id:
        payload["assignees"] = [assignee_id]

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=get_headers(api_key))
        response.raise_for_status()
        work_item = response.json()

    # Add to module if specified
    if module_key and module_key in MODULES:
        module_id = MODULES[module_key]
        await add_to_module(work_item["id"], module_id, api_key)

    # Build the URL for the created item
    sequence_id = work_item.get("sequence_id", "")
    item_url = f"https://app.plane.so/{workspace}/projects/{project_id}/issues/{work_item['id']}"

    return {
        "id": work_item["id"],
        "identifier": f"{PROJECT_CONFIG['project_key']}-{sequence_id}",
        "name": work_item["name"],
        "url": item_url,
        "module": module_key,
    }


async def add_to_module(work_item_id: str, module_id: str, api_key: Optional[str] = None) -> bool:
    """
    Add a work item to a module.

    Args:
        work_item_id: UUID of the work item
        module_id: UUID of the module
        api_key: Optional API key to use

    Returns:
        True if successful
    """
    workspace = PROJECT_CONFIG["workspace_slug"]
    project_id = PROJECT_CONFIG["project_id"]

    url = f"{PLANE_BASE_URL}/workspaces/{workspace}/projects/{project_id}/modules/{module_id}/module-issues/"

    payload = {"issues": [work_item_id]}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=get_headers(api_key))
            response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Error adding work item to module: {e}")
        return False


async def get_cycles(api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get all cycles (sprints) for the project.

    Args:
        api_key: Optional API key to use

    Returns:
        List of cycle dicts with id and name
    """
    workspace = PROJECT_CONFIG["workspace_slug"]
    project_id = PROJECT_CONFIG["project_id"]

    url = f"{PLANE_BASE_URL}/workspaces/{workspace}/projects/{project_id}/cycles/"

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=get_headers(api_key))
        response.raise_for_status()
        return response.json()


async def get_current_cycle(api_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get the current active cycle (sprint) for the project.

    Looks for a cycle that is currently in progress based on start_date and end_date.

    Args:
        api_key: Optional API key to use

    Returns:
        Dict with cycle info (id, name) if found, None otherwise
    """
    from datetime import datetime, date

    try:
        cycles_response = await get_cycles(api_key)
        today = date.today()

        # Handle both list response and paginated response with "results" key
        if isinstance(cycles_response, dict):
            cycles = cycles_response.get("results", [])
        else:
            cycles = cycles_response

        for cycle in cycles:
            start_date_str = cycle.get("start_date")
            end_date_str = cycle.get("end_date")

            if not start_date_str or not end_date_str:
                continue

            # Parse dates - handle ISO format with timestamp (e.g., "2026-01-06T21:06:57.408097Z")
            try:
                # Extract just the date part if it has timestamp
                start_clean = start_date_str.split("T")[0] if "T" in start_date_str else start_date_str
                end_clean = end_date_str.split("T")[0] if "T" in end_date_str else end_date_str

                start_date = datetime.strptime(start_clean, "%Y-%m-%d").date()
                end_date = datetime.strptime(end_clean, "%Y-%m-%d").date()

                # Check if today falls within this cycle
                if start_date <= today <= end_date:
                    logger.info(f"Found active cycle: {cycle.get('name')}")
                    return {
                        "id": cycle.get("id"),
                        "name": cycle.get("name"),
                        "start_date": start_date_str,
                        "end_date": end_date_str,
                    }
            except ValueError as ve:
                logger.warning(f"Could not parse dates for cycle {cycle.get('name')}: {ve}")
                continue

        logger.info("No active cycle found for today's date")
        return None

    except Exception as e:
        logger.error(f"Error getting current cycle: {e}")
        return None


async def add_to_cycle(work_item_id: str, cycle_id: str, api_key: Optional[str] = None) -> bool:
    """
    Add a work item to a cycle (sprint).

    Args:
        work_item_id: UUID of the work item
        cycle_id: UUID of the cycle
        api_key: Optional API key to use

    Returns:
        True if successful
    """
    workspace = PROJECT_CONFIG["workspace_slug"]
    project_id = PROJECT_CONFIG["project_id"]

    url = f"{PLANE_BASE_URL}/workspaces/{workspace}/projects/{project_id}/cycles/{cycle_id}/cycle-issues/"

    payload = {"issues": [work_item_id]}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=get_headers(api_key))
            response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Error adding work item to cycle: {e}")
        return False
