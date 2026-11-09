# Wangku: Android build preparation

This is source code and build setup, NOT a compiled APK. Camera and splash edits
from Wangku_Latest.zip are preserved. Android CAMERA and INTERNET permissions
are added. Generated caches are omitted.

## 1. Build on your Windows computer
Extract this project into a NEW folder. Open PowerShell in that folder (where
pyproject.toml is visible). Run:

    powershell -ExecutionPolicy Bypass -File .\BUILD_ANDROID.ps1

The script installs Flet dependencies and runs `flet build apk` using the installed
console entry point, avoiding PATH shortcut issues. It needs internet and the
Android/Flutter toolchain; Flet may download tools or ask you to install prerequisites
and accept SDK licences. Keep the build output if it fails. No remote software was
installed or APK compiled during preparation of this ZIP.

When successful, find the .apk under build\apk, transfer it to your Android phone,
open it and allow installation from that source when Android asks. This is for
private testing. Preserve the signing key for updates; Play Store distribution
needs a stable application ID and release signing setup.

## 2. Enable AI on the phone
The app no longer reads a Gemini key on the phone. A hosted HTTPS backend is needed.
Other app features can be tried before hosting, but the coach cannot reply yet.

The backend/ folder contains a standalone Python service and Dockerfile. Deploy
that folder to a service supporting Docker web services and HTTPS. Configure these
as server secrets/environment settings, never inside source code or the APK:

    GEMINI_API_KEY = your Google API key
    GEMINI_MODEL = gemini-flash-latest (or an available model for your project)
    WANGKU_ACCESS_TOKENS = a long random access token per tester, comma separated
    PORT = the port expected by the hosting provider (default 8080)

Generate a tester token locally with:
    python -c "import secrets; print(secrets.token_urlsafe(32))"

Use a NEW token, never your Gemini key. Host behind provider-managed HTTPS.
The backend responds at GET /health and POST /coach. It does not log request bodies.
No provider account was created and no backend was deployed during this task.

In Wangku: Jurulatih > Tetapan AI. Enter your hosted HTTPS base URL (without /coach)
and a tester access token. The URL is saved locally; the access token lasts for the
current app session only. Enter it again after restarting. All interface messages
and AI instructions remain Malay. AI-generated language/accuracy cannot be guaranteed.

This is a private-pilot backend: six attempts per minute and 60 per hour per token,
three concurrent provider calls, 64 KiB request cap, server-owned instructions.
Limits are in memory and per process, reset on restart, and are not shared across
replicas. Use a single instance for this pilot. Tokens are bearer credentials;
revoke a tester by removing their token and restarting. Before public distribution,
add real user authentication, durable shared limits and operational monitoring.
Questions and financial summaries are sent to Google. Do not enter sensitive data.

## 3. iPhone
A native iOS build still needs macOS/Xcode and Apple signing/distribution setup.
This Windows script produces Android only.

## Checks performed
Python syntax and TOML parsing; backend/client tests with mocked Gemini, HTTP
authorization and response tests. No live Gemini, APK build, camera-device or
installation test was possible here. Existing local account/storage limitations
remain unchanged. The receipt scanner still requires manual entry after capture.

Run checks: python -m unittest discover -s tests -v
