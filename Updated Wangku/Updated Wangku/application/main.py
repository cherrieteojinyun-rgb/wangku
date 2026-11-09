import asyncio

import flet as ft

from chat import ChatError, reply

BG = "#f7f8fb"
SURFACE = "#ffffff"
INK = "#1f2937"
MUTED = "#6b7280"
PRIMARY = "#6d28d9"
USER_BG = "#6d28d9"
BOT_BG = "#ffffff"


def bubble(sender, text):
    mine = sender == "user"
    return ft.Row(
        [
            ft.Container(
                content=ft.Text(text, color="#ffffff" if mine else INK, selectable=True),
                bgcolor=USER_BG if mine else BOT_BG,
                border=ft.Border.all(1, "#e5e7eb") if not mine else None,
                padding=12,
                border_radius=16,
                width=520,
            )
        ],
        alignment=ft.MainAxisAlignment.END if mine else ft.MainAxisAlignment.START,
    )


async def main(page: ft.Page):
    page.title = "AI Chatbot"
    page.bgcolor = BG
    page.padding = 16
    page.theme_mode = ft.ThemeMode.LIGHT

    state = {"messages": [], "busy": False, "mode": "backend", "backend_url": "", "backend_token": ""}

    messages_view = ft.ListView(expand=True, spacing=10, auto_scroll=True)
    status = ft.Text("", color=MUTED, size=12)
    error = ft.Text("", color="#dc2626", size=12, visible=False)
    input_box = ft.TextField(
        hint_text="Type a message...",
        expand=True,
        multiline=True,
        min_lines=1,
        max_lines=4,
        shift_enter=True,
        border_radius=14,
    )

    mode_dropdown = ft.Dropdown(
        label="Mode",
        value="backend",
        width=220,
        options=[
            ft.dropdown.Option("backend", "Backend (recommended)"),
            ft.dropdown.Option("direct", "Direct Gemini (local dev)"),
        ],
    )
    backend_url = ft.TextField(label="Backend HTTPS URL", hint_text="https://your-server.example", border_radius=12)
    backend_token = ft.TextField(label="Backend access token", password=True, can_reveal_password=True, border_radius=12)

    def render_messages():
        messages_view.controls = [bubble(s, t) for s, t in state["messages"]] or [
            ft.Container(
                content=ft.Text(
                    "Start a conversation. Use backend mode for deployed apps; direct mode requires GEMINI_API_KEY in the environment.",
                    color=MUTED,
                ),
                bgcolor=SURFACE,
                padding=14,
                border_radius=14,
                border=ft.Border.all(1, "#e5e7eb"),
            )
        ]

    def set_busy(busy, text=""):
        state["busy"] = busy
        status.value = text
        input_box.disabled = busy
        send_button.disabled = busy
        clear_button.disabled = busy

    async def send(_=None):
        text = (input_box.value or "").strip()
        if not text or state["busy"]:
            return
        if len(text) > 4000:
            error.value = "Message is too long (max 4000 characters)."
            error.visible = True
            page.update()
            return
        error.value = ""
        error.visible = False
        state["messages"].append(("user", text))
        input_box.value = ""
        set_busy(True, "Thinking...")
        render_messages()
        page.update()
        try:
            answer = await reply(
                state["messages"],
                mode=state["mode"],
                backend_url=state["backend_url"],
                backend_token=state["backend_token"],
            )
            state["messages"].append(("assistant", answer))
        except ChatError as exc:
            error.value = str(exc)
            error.visible = True
        except Exception:
            error.value = "Something went wrong. Try again."
            error.visible = True
        finally:
            set_busy(False)
            render_messages()
            page.update()

    async def clear(_=None):
        if state["busy"]:
            return
        state["messages"] = []
        error.visible = False
        render_messages()
        page.update()

    def save_settings(_=None):
        state["mode"] = mode_dropdown.value or "backend"
        state["backend_url"] = (backend_url.value or "").strip().rstrip("/")
        state["backend_token"] = (backend_token.value or "").strip()
        page.close(settings_dialog)
        direct_note = " Direct mode uses GEMINI_API_KEY from the local environment." if state["mode"] == "direct" else ""
        page.snack_bar = ft.SnackBar(ft.Text("Settings saved." + direct_note))
        page.snack_bar.open = True
        page.update()

    settings_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Chat settings"),
        content=ft.Column(
            [
                mode_dropdown,
                backend_url,
                backend_token,
                ft.Text(
                    "Backend mode keeps API keys on the server. The token is kept in memory for this session only.",
                    size=12,
                    color=MUTED,
                ),
            ],
            tight=True,
            width=420,
            spacing=10,
        ),
        actions=[
            ft.TextButton("Cancel", on_click=lambda _: page.close(settings_dialog)),
            ft.FilledButton("Save", on_click=save_settings),
        ],
    )

    send_button = ft.IconButton(icon=ft.Icons.SEND_ROUNDED, tooltip="Send", on_click=send, icon_color=PRIMARY)
    clear_button = ft.TextButton("Clear", on_click=clear)

    input_box.on_submit = send
    render_messages()

    page.appbar = ft.AppBar(
        title=ft.Text("AI Chatbot", weight=ft.FontWeight.BOLD),
        bgcolor=SURFACE,
        actions=[
            ft.IconButton(ft.Icons.SETTINGS_OUTLINED, tooltip="Settings", on_click=lambda _: page.open(settings_dialog)),
            clear_button,
        ],
    )
    page.add(
        ft.Column(
            [
                messages_view,
                error,
                status,
                ft.Row([input_box, send_button], vertical_alignment=ft.CrossAxisAlignment.END),
            ],
            expand=True,
            spacing=8,
        )
    )


if __name__ == "__main__":
    ft.run(main)
