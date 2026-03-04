import logging
import time
import base64
import httpx
from typing import Optional, List, Dict, Any

from config import JIRA_EMAIL, JIRA_API_TOKEN, JIRA_CLOUD_ID, JIRA_SITE_URL

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

PROJECTS = {
    "TUNI": {"id": "10052", "key": "TUNI", "board_id": 33},
    "ALZ":  {"id": "10184", "key": "ALZ", "board_id": None},
    "TICH": {"id": "10036", "key": "TICH", "board_id": None},
    "VIA":  {"id": "10049", "key": "VIA", "board_id": None},
}

TEAM_MEMBERS = {
    "juan": "712020:98d3a4a5-6a5a-4aeb-9562-99b23026769c",
    "alejo": "712020:f1ac8489-822d-4d13-9ec6-87cdbe0ccad4",
    "leonardo": "712020:0d30fcc7-8a2c-41fd-b5ac-f6684246caa8",
    "rocio": "712020:2308197a-ffa9-4ee4-92e0-a1c6d1709337",
    "francisco": "712020:7319b298-7da2-43b8-b6b7-b32a0fec6f6a",
    "sebastian": "712020:58c089e2-fd67-4f6a-890b-5007df236751",
    "jose": "712020:a3a4d5e5-f779-4225-a164-095114adcd77",
    "julian": "712020:3fdee20f-9acf-4249-b848-b06124af5363",
    "joaquin": "712020:6f09bade-95d7-4098-b626-5c256c0a3b39",
}

# Email de Slack → Jira account ID (para setear reporter)
TEAM_EMAILS = {
    "juan.mateos@educabot.com": "712020:98d3a4a5-6a5a-4aeb-9562-99b23026769c",
    "alejo.bonadeo@educabot.com": "712020:f1ac8489-822d-4d13-9ec6-87cdbe0ccad4",
    "leonardo.cano@educabot.com": "712020:0d30fcc7-8a2c-41fd-b5ac-f6684246caa8",
    "rocio.etchebarne@educabot.com": "712020:2308197a-ffa9-4ee4-92e0-a1c6d1709337",
    "francisco.conte@educabot.com": "712020:7319b298-7da2-43b8-b6b7-b32a0fec6f6a",
    "sebastian.luser@educabot.com": "712020:58c089e2-fd67-4f6a-890b-5007df236751",
    "jose.attento@educabot.com": "712020:a3a4d5e5-f779-4225-a164-095114adcd77",
    "julian.quinteiro@educabot.com": "712020:3fdee20f-9acf-4249-b848-b06124af5363",
    "joaquin.brito@educabot.com": "712020:6f09bade-95d7-4098-b626-5c256c0a3b39",
}

EPICS = {
    "TUNI": {
        "mejoras_clase": "TUNI-1007",
        "mejoras_contenido": "TUNI-1008",
        "mobile": "TUNI-1009",
        "supervisores": "TUNI-1010",
        "perfil": "TUNI-1011",
        "comunidad": "TUNI-1012",
        "analisis_conversaciones": "TUNI-1013",
    },
    "TICH": {
        "ktlo": "TICH-771",
        "admin": "TICH-801",
        "excelencia_tecnica": "TICH-811",
        "pagos": "TICH-813",
    },
}

EPIC_KEYWORDS = {
    "TUNI": {
        "mejoras_clase": ["clase", "aula", "sesión", "sesion", "live"],
        "mejoras_contenido": ["contenido", "actividad", "ejercicio", "quiz", "experiencia"],
        "mobile": ["mobile", "app", "celular", "responsive"],
        "supervisores": ["supervisor", "dashboard", "monitoreo"],
        "perfil": ["perfil", "usuario", "cuenta", "configuración", "configuracion"],
        "comunidad": ["comunidad", "social", "foro", "amigos"],
        "analisis_conversaciones": ["análisis", "analisis", "conversación", "conversacion", "tutor", "ia", "chat", "prompt"],
    },
    "TICH": {
        "ktlo": ["bug", "fix", "urgente", "hotfix", "mantenimiento"],
        "admin": ["admin", "administrador", "backoffice"],
        "excelencia_tecnica": ["refactor", "deuda técnica", "deuda tecnica", "performance", "testing"],
        "pagos": ["pago", "suscripción", "suscripcion", "factura", "billing"],
    },
}

ISSUE_TYPES = {
    "tarea": "10007",
    "subtarea": "10008",
    "historia": "10006",
    "error": "10009",
    "epic": "10000",
    "design": "10079",
    "qa": "10112",
}

PRIORITY_MAP = {
    "urgent": "1",
    "high": "2",
    "medium": "3",
    "low": "4",
    "none": "4",
}

# =============================================================================
# CACHE
# =============================================================================

_cache: Dict[str, Dict[str, Any]] = {}

def _get_cached(key: str, ttl_seconds: int) -> Optional[Any]:
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"]) < ttl_seconds:
        return entry["value"]
    return None

def _set_cached(key: str, value: Any):
    _cache[key] = {"value": value, "ts": time.time()}

# =============================================================================
# API HELPERS
# =============================================================================

def get_headers() -> Dict[str, str]:
    credentials = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode()).decode()
    return {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

def _base_url() -> str:
    return f"https://api.atlassian.com/ex/jira/{JIRA_CLOUD_ID}"

def _parse_inline(text: str) -> List[Dict[str, Any]]:
    """Parse inline markdown (bold, italic, code) into ADF text nodes."""
    import re
    nodes = []
    # Pattern: **bold**, *italic*, `code`
    pattern = re.compile(r'(\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`)')
    last_end = 0
    for match in pattern.finditer(text):
        # Add plain text before this match
        if match.start() > last_end:
            plain = text[last_end:match.start()]
            if plain:
                nodes.append({"type": "text", "text": plain})
        if match.group(2):  # **bold**
            nodes.append({"type": "text", "text": match.group(2), "marks": [{"type": "strong"}]})
        elif match.group(3):  # *italic*
            nodes.append({"type": "text", "text": match.group(3), "marks": [{"type": "em"}]})
        elif match.group(4):  # `code`
            nodes.append({"type": "text", "text": match.group(4), "marks": [{"type": "code"}]})
        last_end = match.end()
    # Remaining text
    if last_end < len(text):
        remaining = text[last_end:]
        if remaining:
            nodes.append({"type": "text", "text": remaining})
    return nodes if nodes else [{"type": "text", "text": text}]


def _text_to_adf(text: str) -> Dict[str, Any]:
    """Convert markdown-like text to Atlassian Document Format (ADF)."""
    import re
    lines = text.split("\n") if text else [""]
    content = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Empty line → skip (don't add empty paragraphs between blocks)
        if not stripped:
            i += 1
            continue

        # Heading: ## Text or ### Text
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
        if heading_match:
            level = len(heading_match.group(1))
            content.append({
                "type": "heading",
                "attrs": {"level": level},
                "content": _parse_inline(heading_match.group(2))
            })
            i += 1
            continue

        # Horizontal rule: --- or ***
        if re.match(r'^(-{3,}|\*{3,})$', stripped):
            content.append({"type": "rule"})
            i += 1
            continue

        # Bullet list: collect consecutive lines starting with - or *
        if re.match(r'^[-*]\s+', stripped):
            list_items = []
            while i < len(lines) and re.match(r'^\s*[-*]\s+', lines[i]):
                item_text = re.sub(r'^\s*[-*]\s+', '', lines[i]).strip()
                list_items.append({
                    "type": "listItem",
                    "content": [{"type": "paragraph", "content": _parse_inline(item_text)}]
                })
                i += 1
            content.append({"type": "bulletList", "content": list_items})
            continue

        # Ordered list: collect consecutive lines starting with 1. 2. etc.
        if re.match(r'^\d+\.\s+', stripped):
            list_items = []
            while i < len(lines) and re.match(r'^\s*\d+\.\s+', lines[i]):
                item_text = re.sub(r'^\s*\d+\.\s+', '', lines[i]).strip()
                list_items.append({
                    "type": "listItem",
                    "content": [{"type": "paragraph", "content": _parse_inline(item_text)}]
                })
                i += 1
            content.append({"type": "orderedList", "content": list_items})
            continue

        # Regular paragraph with inline formatting
        content.append({
            "type": "paragraph",
            "content": _parse_inline(stripped)
        })
        i += 1

    if not content:
        content = [{"type": "paragraph", "content": [{"type": "text", "text": ""}]}]

    return {"version": 1, "type": "doc", "content": content}

# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def suggest_epic(text: str, project_key: str) -> Optional[str]:
    keywords_map = EPIC_KEYWORDS.get(project_key)
    if not keywords_map:
        return None
    text_lower = text.lower()
    for epic_key, keywords in keywords_map.items():
        for keyword in keywords:
            if keyword in text_lower:
                return epic_key
    return None

def resolve_assignee(name: str) -> Optional[str]:
    name_lower = name.lower().strip()
    for member_name, member_id in TEAM_MEMBERS.items():
        if member_name in name_lower or name_lower in member_name:
            return member_id
    return None

def resolve_reporter(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    return TEAM_EMAILS.get(email)

async def get_active_sprint(board_id: int) -> Optional[Dict[str, Any]]:
    cache_key = f"sprint_{board_id}"
    cached = _get_cached(cache_key, ttl_seconds=3600)
    if cached is not None:
        return cached

    url = f"https://api.atlassian.com/ex/jira/{JIRA_CLOUD_ID}/rest/agile/1.0/board/{board_id}/sprint?state=active"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=get_headers())
            response.raise_for_status()
            data = response.json()
            sprints = data.get("values", [])
            result = sprints[0] if sprints else None
            _set_cached(cache_key, result)
            return result
    except Exception as e:
        logger.error(f"Error getting active sprint for board {board_id}: {e}")
        return None

async def search_parent_stories(project_key: str, epic_key: str) -> List[Dict[str, str]]:
    cache_key = f"stories_{project_key}_{epic_key}"
    cached = _get_cached(cache_key, ttl_seconds=1800)
    if cached is not None:
        return cached

    jql = f'project = {project_key} AND issuetype = Story AND "Epic Link" = {epic_key} AND status != Done ORDER BY updated DESC'
    url = f"{_base_url()}/rest/api/3/search?jql={jql}&fields=key,summary&maxResults=20"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=get_headers())
            response.raise_for_status()
            data = response.json()
            stories = [
                {"key": issue["key"], "summary": issue["fields"]["summary"]}
                for issue in data.get("issues", [])
            ]
            _set_cached(cache_key, stories)
            return stories
    except Exception as e:
        logger.error(f"Error searching parent stories: {e}")
        return []

async def create_issue(
    title: str,
    description: str = "",
    assignee_id: Optional[str] = None,
    epic_key: Optional[str] = None,
    priority: str = "none",
    project_key: str = "TUNI",
    issue_type: str = "tarea",
    sprint_id: Optional[int] = None,
    parent_key: Optional[str] = None,
    requester_info: Optional[Dict[str, str]] = None,
    reporter_id: Optional[str] = None,
) -> Dict[str, Any]:
    project = PROJECTS.get(project_key)
    if not project:
        raise ValueError(f"Unknown project: {project_key}")

    # Build description with requester info
    desc_text = description
    if requester_info and requester_info.get("name"):
        requester_note = f"Solicitado por: {requester_info['name']}"
        if requester_info.get("email"):
            requester_note += f" ({requester_info['email']})"
        desc_text = f"{requester_note}\n---\n{description}" if description else requester_note

    # Determine parent: subtarea uses parent_key, other types use epic_key
    issue_type_id = ISSUE_TYPES.get(issue_type, ISSUE_TYPES["tarea"])
    parent = None
    if issue_type == "subtarea" and parent_key:
        parent = {"key": parent_key}
    elif epic_key:
        parent = {"key": epic_key}

    payload: Dict[str, Any] = {
        "fields": {
            "project": {"id": project["id"]},
            "summary": title,
            "description": _text_to_adf(desc_text),
            "issuetype": {"id": issue_type_id},
            "priority": {"id": PRIORITY_MAP.get(priority, "4")},
        }
    }

    if parent:
        payload["fields"]["parent"] = parent

    if assignee_id:
        payload["fields"]["assignee"] = {"accountId": assignee_id}

    if reporter_id:
        payload["fields"]["reporter"] = {"accountId": reporter_id}

    if sprint_id:
        payload["fields"]["customfield_10020"] = sprint_id

    url = f"{_base_url()}/rest/api/3/issue"
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=get_headers())
        response.raise_for_status()
        result = response.json()

    issue_key = result.get("key", "")
    return {
        "id": result.get("id"),
        "key": issue_key,
        "name": title,
        "url": f"{JIRA_SITE_URL}/browse/{issue_key}",
        "epic": epic_key,
        "project": project_key,
        "issue_type": issue_type,
        "parent_story": parent_key,
    }
