# Slack Bot para Plane (TUNI)

Bot de Slack que crea tickets en Plane cuando lo mencionas en un hilo.

## Uso

En cualquier hilo de Slack:
```
@PlaneBot crea un ticket sobre esto
@PlaneBot ticket para Juan sobre el bug del login
@PlaneBot asigname este ticket de integración
```

El bot:
1. Lee el contexto del hilo
2. Usa Claude para interpretar y extraer información
3. Crea el ticket en Plane con título, descripción, módulo y asignado
4. Responde con el link al ticket

## Setup

### 1. Crear Slack App

1. Ve a https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. Nombra tu app (ej: "PlaneBot") y selecciona tu workspace

### 2. Configurar permisos (OAuth & Permissions)

Agrega estos Bot Token Scopes:
- `app_mentions:read` - Recibir menciones
- `chat:write` - Enviar mensajes
- `channels:history` - Leer hilos en canales públicos
- `groups:history` - Leer hilos en canales privados
- `users:read` - Obtener nombres de usuarios

### 3. Habilitar Socket Mode

1. Ve a "Socket Mode" en el menú lateral
2. Habilita Socket Mode
3. Crea un App-Level Token con scope `connections:write`
4. Guarda el token (empieza con `xapp-`)

### 4. Suscribirse a eventos

1. Ve a "Event Subscriptions"
2. Habilita eventos
3. En "Subscribe to bot events" agrega:
   - `app_mention`

### 5. Instalar la app

1. Ve a "Install App"
2. Click "Install to Workspace"
3. Copia el Bot User OAuth Token (empieza con `xoxb-`)

### 6. Configurar variables de entorno

```bash
cp .env.example .env
```

Edita `.env` con tus tokens:
```
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
ANTHROPIC_API_KEY=sk-ant-...
PLANE_API_KEY=...
PLANE_WORKSPACE_SLUG=tu-workspace
```

### 7. Instalar dependencias

```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 8. Ejecutar

```bash
python app.py
```

## Deploy en Railway

1. Crea un repo en GitHub con este código
2. Ve a https://railway.app
3. "New Project" → "Deploy from GitHub repo"
4. Selecciona el repo
5. Agrega las variables de entorno en Settings → Variables
6. Railway desplegará automáticamente

## Estructura

```
SlackBotPlane/
├── app.py                 # Entry point
├── config.py              # Variables de entorno
├── handlers/
│   └── mention_handler.py # Maneja @menciones
├── services/
│   ├── slack_service.py   # Interacción con Slack
│   ├── llm_service.py     # Claude tool use
│   └── plane_service.py   # API de Plane
├── requirements.txt
└── .env.example
```

## Módulos soportados

El bot infiere automáticamente el módulo basado en keywords:

| Keywords | Módulo |
|----------|--------|
| chat, conversación, tutor, IA | Tutor conversacional |
| actividad, ejercicio, quiz | Experiencias educativas |
| métricas, progreso, insignias | Modelo del estudiante |
| video, multimedia | Videos educativos |
| perfil, amigos, social | Comunidad |
| dashboard, supervisor | Supervisores |
| notificación, whatsapp, email | Notificación |
| integración, api, sso | Integración |
| proceso, equipo, mejora | Equipo y mejora |

## Equipo

El bot reconoce a estos miembros para asignación:
- Juan
- Rocío (UX/UI)
- Francisco (QA)
- Alejo
- Leonardo
- Pablo
