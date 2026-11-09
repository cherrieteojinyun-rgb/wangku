import asyncio
import base64
import json
import mimetypes
import re
from pathlib import Path

import flet as ft

from chat_client import ChatTransportError, post_gemini
from theme import BG, INK, MUTED, PRIMARY, PURPLE_SOFT, SURFACE

_CATEGORY_LABELS = (
    "Makanan", "Pengangkutan", "Hiburan", "Buku", "Lain-lain"
)

_CATEGORY_MAP = {
    "food": "Makanan",
    "makanan": "Makanan",
    "transport": "Pengangkutan",
    "pengangkutan": "Pengangkutan",
    "fun": "Hiburan",
    "entertainment": "Hiburan",
    "hiburan": "Hiburan",
    "books": "Buku",
    "book": "Buku",
    "buku": "Buku",
    "other": "Lain-lain",
    "lain": "Lain-lain",
    "lain-lain": "Lain-lain",
}

_REVIEWS = {}


def _photo_key(photo):
    return str(photo or "")


def _image_payload(photo):
    value = str(photo or "")

    if value.startswith("data:") and "," in value:
        header, encoded = value.split(",", 1)
        match = re.match(r"data:([^;]+);base64", header)

        if not match:
            raise ValueError("Invalid image data")

        return match.group(1), encoded

    path = Path(value)

    if not path.is_file():
        raise ValueError("Image file not found")

    mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"

    encoded = base64.b64encode(path.read_bytes()).decode("ascii")

    return mime_type, encoded


def _parse_items(response):
    text = response.strip()

    if text.startswith("```"):
        text = re.sub(
            r"^```(?:json)?\s*|\s*```$",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()

    result = json.loads(text)

    if not isinstance(result, dict):
        raise ValueError("Invalid response")

    if not isinstance(result.get("items"), list):
        raise ValueError("Missing items")

    items = []

    for item in result["items"]:
        if not isinstance(item, dict):
            continue

        description = str(item.get("description", "")).strip()
        raw_price = item.get("price", item.get("amount"))

        try:
            price = float(
                str(raw_price)
                .replace(",", "")
                .replace("RM", "")
                .strip()
            )
        except (TypeError, ValueError):
            continue

        if not description or price <= 0:
            continue

        raw_category = str(
            item.get("category", "Other")
        ).strip().casefold()

        items.append({
            "description": description,
            "amount": f"{price:.2f}",
            "category": _CATEGORY_MAP.get(
                raw_category, "Lain-lain"
            ),
        })

    return items


def _update_status(review):
    control = review.get("status_control")

    if control is None:
        return

    control.value = review["status"]

    control.color = (
        PRIMARY if review["running"]
        else (
            MUTED if review["status"].startswith("Tidak")
            else PRIMARY
        )
    )

    progress = review.get("progress_control")

    if progress is not None:
        progress.visible = review["running"]

    try:
        if control.page:
            control.page.update()
    except (AttributeError, RuntimeError):
        pass


async def _analyze(photo, review):
    review["running"] = True
    review["status"] = "Menganalisis resit..."
    _update_status(review)

    try:
        mime_type, image_data = await asyncio.to_thread(
            _image_payload, photo
        )

        contents = [{
            "role": "user",
            "parts": [
                {
                    "text": (
                        'Extract every purchased line item and its individual price. '
                        'Return JSON only in this format: '
                        '{"items":[{"description":"item","price":0.00,'
                        '"category":"Food|Transport|Fun|Books|Other"}]}. '
                        'Use individual item prices, not the receipt total. '
                        'Do not guess unreadable prices. '
                        'If this is not a receipt, return {"items":[]}.'
                    )
                },
                {
                    "inlineData": {
                        "mimeType": mime_type,
                        "data": image_data,
                    }
                },
            ],
        }]

        response = await asyncio.to_thread(
            post_gemini,
            contents,
            system_instruction=(
                "You accurately extract receipt line items. "
                "Return valid JSON only. Never invent prices."
            ),
        )

        items = _parse_items(response)

        if items:
            review["items"] = items
            review["status"] = (
                f"{len(items)} item dikesan. "
                "Sila semak butiran."
            )
            _render_items(review)
        else:
            review["status"] = (
                "Tiada item dapat dibaca. "
                "Tambah item secara manual."
            )

    except ChatTransportError as error:
        messages = {
            "missing_key": "Gagal: GEMINI_API_KEY belum ditetapkan.",
            "network": "Gagal: Masalah sambungan internet.",
            "rate_limit": "Gagal: Had penggunaan AI dicapai.",
            "unauthorized": "Gagal: Kunci Gemini tidak sah.",
            "empty": "AI tidak dapat membaca resit.",
        }

        review["status"] = messages.get(
            str(error),
            "Analisis AI gagal. Tambah item secara manual.",
        )

    except Exception as error:
        logging_message = str(error)
        print("Receipt analysis error:", logging_message)

        review["status"] = (
            "Analisis gagal. Tambah item secara manual."
        )

    finally:
        review["running"] = False
        _update_status(review)


def _make_item_controls(review):
    controls = []

    for index, item in enumerate(review["items"]):

        def change_field(field, event, idx=index):
            review["items"][idx][field] = event.control.value

        def remove_item(event, idx=index):
            if len(review["items"]) <= 1:
                review["items"] = [{
                    "description": "",
                    "amount": "",
                    "category": "Makanan",
                }]
            else:
                review["items"].pop(idx)

            _render_items(review)

        description_field = ft.TextField(
            value=item.get("description", ""),
            label="Nama item",
            hint_text="Contoh: Nasi ayam",
            border_radius=12,
            expand=True,
            on_change=lambda e, fn=change_field: fn(
                "description", e
            ),
        )

        amount_field = ft.TextField(
            value=str(item.get("amount", "")),
            label="Harga (RM)",
            prefix=ft.Text("RM "),
            keyboard_type=ft.KeyboardType.NUMBER,
            border_radius=12,
            expand=True,
            on_change=lambda e, fn=change_field: fn(
                "amount", e
            ),
        )

        category_field = ft.Dropdown(
            value=item.get("category", "Makanan"),
            label="Kategori",
            options=[
                ft.DropdownOption(text=name)
                for name in _CATEGORY_LABELS
            ],
            border_radius=12,
            expand=True,
            on_change=lambda e, fn=change_field: fn(
                "category", e
            ),
        )

        controls.append(
            ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                description_field,
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE,
                                    tooltip="Padam item",
                                    on_click=remove_item,
                                ),
                            ],
                            spacing=6,
                            vertical_alignment=ft.CrossAxisAlignment.END,
                        ),
                        ft.Row(
                            [
                                amount_field,
                                category_field,
                            ],
                            spacing=8,
                        ),
                    ],
                    spacing=8,
                    tight=True,
                ),
                padding=12,
                bgcolor=SURFACE,
                border_radius=14,
            )
        )

    return controls


def _render_items(review):
    column = review.get("items_control")

    if column is None:
        return

    column.controls = _make_item_controls(review)

    try:
        if column.page:
            column.page.update()
    except (AttributeError, RuntimeError):
        pass


def get_items(photo):
    """Return the editable receipt items for main.py."""
    review = _REVIEWS.get(_photo_key(photo))

    if not review:
        return []

    return [
        dict(item)
        for item in review["items"]
    ]


def live(camera, camera_status, on_capture, on_cancel):
    return ft.Column(
        [
            ft.TextButton(
                "← Kembali",
                on_click=on_cancel,
            ),
            ft.Text(
                "Imbas resit",
                size=26,
                weight=ft.FontWeight.BOLD,
                color=INK,
            ),
            ft.Text(
                "Letakkan resit di hadapan kamera.",
                color=MUTED,
            ),
            ft.Container(
                content=camera,
                border_radius=16,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            ),
            camera_status,
            ft.FilledButton(
                "Ambil gambar",
                icon=ft.Icons.CAMERA_ALT,
                on_click=on_capture,
                style=ft.ButtonStyle(
                    bgcolor=PRIMARY,
                    color=ft.Colors.WHITE,
                ),
            ),
        ],
        spacing=14,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )


def review(photo, on_save, on_retake, on_cancel):
    key = _photo_key(photo)

    if key not in _REVIEWS:
        _REVIEWS[key] = {
            "items": [{
                "description": "",
                "amount": "",
                "category": "Makanan",
            }],
            "running": False,
            "status": "Menunggu analisis resit...",
            "status_control": None,
            "progress_control": None,
            "items_control": None,
        }

    data = _REVIEWS[key]

    status = ft.Text(
        data["status"],
        size=12,
        color=PRIMARY,
    )

    progress = ft.ProgressRing(
        width=18,
        height=18,
        stroke_width=2,
        visible=data["running"],
    )

    items_column = ft.Column(
        controls=[],
        spacing=10,
        tight=True,
    )

    data["status_control"] = status
    data["progress_control"] = progress
    data["items_control"] = items_column

    _render_items(data)

    def add_item(event):
        data["items"].append({
            "description": "",
            "amount": "",
            "category": "Makanan",
        })
        _render_items(data)

    screen = ft.Column(
        [
            ft.TextButton(
                "← Kembali ke transaksi",
                on_click=on_cancel,
            ),
            ft.Text(
                "Semak pembelian anda",
                size=26,
                weight=ft.FontWeight.BOLD,
                color=INK,
            ),
            ft.Text(
                "Semak gambar dan betulkan item serta harga "
                "sebelum menghantar.",
                color=MUTED,
            ),
            ft.Container(
                content=ft.Image(
                    src=photo,
                    height=185,
                    fit=ft.ImageFit.CONTAIN,
                ),
                padding=10,
                bgcolor=SURFACE,
                border_radius=14,
            ),
            ft.Row(
                [
                    progress,
                    status,
                ],
                spacing=10,
            ),
            ft.Text(
                "Senarai item",
                size=17,
                weight=ft.FontWeight.BOLD,
                color=INK,
            ),
            items_column,
            ft.OutlinedButton(
                "Tambah item",
                icon=ft.Icons.ADD,
                on_click=add_item,
            ),
            ft.Row(
                [
                    ft.OutlinedButton(
                        "Ambil semula",
                        icon=ft.Icons.CAMERA_ALT,
                        on_click=on_retake,
                    ),
                    ft.Container(expand=True),
                    ft.FilledButton(
                        "Hantar",
                        icon=ft.Icons.CHECK,
                        on_click=on_save,
                        style=ft.ButtonStyle(
                            bgcolor=PRIMARY,
                            color=ft.Colors.WHITE,
                        ),
                    ),
                ],
                wrap=True,
                spacing=8,
            ),
        ],
        spacing=13,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    if not data["running"] and data["status"] == "Menunggu analisis resit...":
        asyncio.create_task(_analyze(photo, data))

    return screen


__all__ = ["live", "review", "get_items"]
