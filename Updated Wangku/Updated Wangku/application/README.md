# AI Chatbot (`/application`)

Standalone AI chatbot added to the Wangku workspace.

## Run

From the workspace root (`C:\p`), with Flet installed:

```powershell
python application/main.py
```

Or, if you use the project environment:

```powershell
flet run application
```

## Modes

- **Backend (recommended):** Uses a Wangku-compatible HTTPS `POST /coach` endpoint. Configure the backend base URL and access token in Settings. API keys stay on the server.
- **Direct Gemini (local development only):** Calls Gemini with `GEMINI_API_KEY` from the environment. Do not use direct mode in distributed apps.

Example (local direct mode):

```powershell
$env:GEMINI_API_KEY = "your-local-dev-key"
$env:GEMINI_MODEL = "gemini-flash-latest"   # optional
python application/main.py
```

## Notes

- Messages are kept in memory for the current session.
- Backend mode expects the same contract as `backend/server.py` (`/health`, `/coach`, bearer token).
- Do not put Gemini API keys in source code or client settings intended for distribution.
