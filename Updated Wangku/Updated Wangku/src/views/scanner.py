import asyncio
import base64
import json
import mimetypes
import re
from pathlib import Path

import flet as ft

from chat_client import ChatTransportError, post_gemini
from theme import CORAL, MINT, MUTED, PRIMARY, PURPLE_SOFT, card, label, primary_button, title

_CATEGORY_LABELS = ("Makanan", "Pengangkutan", "Hiburan", "Buku", "Lain-lain")
_CATEGORY_MAP = {
    "food": "Makanan", "makanan": "Makanan", "transport": "Pengangkutan",
    "pengangkutan": "Pengangkutan", "fun": "Hiburan", "entertainment": "Hiburan",
    "hiburan": "Hiburan", "books": "Buku", "book": "Buku", "buku": "Buku",
    "other": "Lain-lain", "lain-lain": "Lain-lain", "lain": "Lain-lain",
}
_REVIEW_STATES = {}
_SUBMITTING = set()
_SUBMITTED = set()


def _photo_key(photo):
    return str(photo or "")


def _read_image(photo):
    value = str(photo or "")
    if value.startswith("data:") and "," in value:
        header, encoded = value.split(",", 1)
        match = re.match(r"data:([^;]+);base64", header)
        if not match:
            raise ValueError("bad_image")
        return match.group(1), encoded
    path = Path(value)
    if not path.is_file():
        raise ValueError("bad_image")
    mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return mime_type, base64.b64encode(path.read_bytes()).decode("ascii")


def _parse_items(response):
    text = response.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()
    result = json.loads(text)
    if not isinstance(result, dict) or not isinstance(result.get("items"), list):
        raise ValueError("invalid_json")
    items = []
    for item in result["items"]:
        if not isinstance(item, dict):
            continue
        description = str(item.get("description", "")).strip()
        price = item.get("price", item.get("amount"))
        try:
            price = float(str(price).replace(",", "").replace("RM", "").strip())
        except (TypeError, ValueError):
            continue
        if not description or price <= 0:
            continue
        category = str(item.get("category", "Other")).strip().casefold()
        items.append({
            "description": description,
            "amount": f"{price:.2f}",
            "category": _CATEGORY_MAP.get(category, "Lain-lain"),
        })
    return items


async def _analyze(photo, review_state):
    review_state["running"] = True
    review_state["status"] = "Menganalisis resit…"
    _refresh_review(review_state)
    try:
        mime_type, image_data = await asyncio.to_thread(_read_image, photo)
        contents = [{
            "role": "user",
            "parts": [
                {"text": "Extract purchased line items from this receipt. Return only JSON in this exact shape: {\"items\":[{\"description\":\"item name\",\"price\":0.00,\"category\":\"Food|Transport|Fun|Books|Other\"}]}. Use each item's individual price, not the receipt total. If the image is not a readable receipt, return {\"items\":[]}. Do not include markdown or commentary."},
                {"inline_data": {"mime_type": mime_type, "data": image_data}},
            ],
        }]
        response = await asyncio.to_thread(
            post_gemini,
            contents,
            system_instruction="You extract receipt purchases accurately. Return valid JSON only, never infer unreadable prices.",
        )
        items = _parse_items(response)
        if items:
            review_state["items"] = items
            review_state["status"] = f"{len(items)} item dikesan. Sila semak dan betulkan jika perlu."
        else:
            review_state["status"] = "Tidak dapat membaca item resit. Tambah item secara manual."
    except ChatTransportError as error:
        messages = {
            "missing_key": "Gagal: Tetapkan GEMINI_API_KEY untuk analisis resit.",
            "network": "Gagal: Sambungan rangkaian bermasalah. Tambah item secara manual.",
            "rate_limit": "Gagal: Had penggunaan AI dicapai. Tambah item secara manual.",
            "unauthorized": "Gagal: Kunci Gemini tidak sah. Tambah item secara manual.",
            "empty": "Tidak dapat membaca resit. Tambah item secara manual.",
        }
        review_state["status"] = messages.get(str(error), "Gagal: Analisis AI tidak tersedia. Tambah item secara manual.")
    except (ValueError, OSError, TypeError, json.JSONDecodeError):
        review_state["status"] = "Tidak dapat membaca resit atau jawapan AI tidak sah. Tambah item secara manual."
    except Exception:
        review_state["status"] = "Gagal: Ralat analisis berlaku. Tambah item secara manual."
    finally:
        review_state["running"] = False
        _refresh_review(review_state)


def _refresh_review(review_state):
    status_control = review_state.get("status_control")
    items_column = review_state.get("items_column")
    if status_control is None or items_column is None:
        return
    status_control.value = review_state["status"]
    status_control.color = PRIMARY if review_state["running"] else (
        CORAL if review_state["status"].startswith(("Gagal", "Tidak")) else MINT
    )
    items_column.controls = [
        _item_entry(index, item, review_state) for index, item in enumerate(review_state["items"])
    ]
    try:
        status_control.page.update()
    except (AttributeError, RuntimeError):
        pass


def _item_entry(index, item, review_state):
    def change(field, value):
        review_state["items"][index][field] = value

    def remove(_event):
        if len(review_state["items"]) > 1:
            review_state["items"].pop(index)
            _refresh_review(review_state)

    return card(ft.Column([
        ft.Row([
            ft.TextField(
                value=item.get("description", ""), label="Nama item", hint_text="cth. Nasi ayam",
                border_radius=12, expand=True,
                on_change=lambda e: change("description", e.control.value),
            ),
            ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, tooltip="Padam item", on_click=remove),
        ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.END),
        ft.Row([
            ft.TextField(
                value=str(item.get("amount", "")), label="Harga (RM)", prefix=ft.Text("RM "),
                keyboard_type=ft.KeyboardType.NUMBER, border_radius=12, expand=True,
                on_change=lambda e: change("amount", e.control.value),
            ),
            ft.Dropdown(
                value=item.get("category", "Makanan"), label="Kategori",
                options=[ft.DropdownOption(text=name) for name in _CATEGORY_LABELS],
                border_radius=12, expand=True,
                on_change=lambda e: change("category", e.control.value),
            ),
        ], spacing=8),
    ], spacing=8, tight=True), padding=12)


def review(photo, description, amount, category, message, on_save, on_retake, on_cancel):
    key = _photo_key(photo)
    review_state = _REVIEW_STATES.setdefault(key, {
        "items": [], "status": "Menunggu analisis resit…", "running": False, "started": False,
    })
    # Keep manual changes and AI results across page rebuilds, but never start a second request.
    if not review_state["items"] and description is not None and (description.value or "").strip():
        review_state["items"] = [{
            "description": description.value or "",
            "amount": amount.value or "" if amount is not None else "",
            "category": category.value or "Makanan" if category is not None else "Makanan",
        }]

    status_control = ft.Text(review_state["status"], size=12, color=PRIMARY)
    items_column = ft.Column(spacing=10, tight=True)
    review_state["status_control"] = status_control
    review_state["items_column"] = items_column

    def redraw_items():
        items_column.controls = [
            _item_entry(index, item, review_state) for index, item in enumerate(review_state["items"])
        ]
        try:
            items_column.page.update()
        except (AttributeError, RuntimeError):
            pass

    def add_item(_event):
        review_state["items"].append({"description": "", "amount": "", "category": "Makanan"})
        redraw_items()

    async def submit(_event=None):
        if key in _SUBMITTING or key in _SUBMITTED:
            return
        entries = review_state["items"]
        valid = []
        for item in entries:
            name = (item.get("description") or "").strip()
            raw_amount = item.get("amount")
            try:
                value = float(str(raw_amount).replace(",", "").replace("RM", "").strip())
            except (TypeError, ValueError):
                value = 0
            if not name or value <= 0:
                message.value = "Lengkapkan keterangan dan harga yang melebihi RM 0 untuk setiap item."
                try:
                    message.page.update()
                except (AttributeError, RuntimeError):
                    pass
                return
            valid.append((name, value, item.get("category", "Makanan")))
        if not valid:
            message.value = "Tambah sekurang-kurangnya satu item yang sah sebelum menghantar."
            try:
                message.page.update()
            except (AttributeError, RuntimeError):
                pass
            return
        _SUBMITTING.add(key)
        _SUBMITTED.add(key)
        try:
            for name, value, item_category in valid:
                description.value = name
                amount.value = str(value)
                category.value = item_category
                await on_save()
        finally:
            _SUBMITTING.discard(key)

    redraw_items()
    if not review_state["started"]:
        review_state["started"] = True
        review_state["task"] = asyncio.create_task(_analyze(photo, review_state))

    return ft.Column([
        title("Semak pembelian anda", size=27),
        label("Semak gambar dan setiap item. Anda boleh mengubah atau menambah butiran sebelum menghantar.", color=MUTED),
        card(ft.Image(src=photo, height=185, fit=ft.BoxFit.CONTAIN, border_radius=16), padding=10),
        ft.OutlinedButton(content=ft.Text("Ambil semula"), icon=ft.Icons.CAMERA_ALT, on_click=on_retake),
        card(ft.Row([
            ft.ProgressRing(size=16, stroke_width=2, color=PRIMARY, visible=review_state["running"]),
            status_control,
        ], spacing=8), color=PURPLE_SOFT, padding=12),
        items_column,
        ft.OutlinedButton(content=ft.Text("Tambah item"), icon=ft.Icons.ADD, on_click=add_item),
        message,
        ft.Row([primary_button("Hantar", submit, icon=ft.Icons.CHECK)], alignment=ft.MainAxisAlignment.END),
    ], spacing=13, horizontal_alignment=ft.CrossAxisAlignment.STRETCH, tight=True)


def live(camera, status, on_capture, on_cancel):
    return ft.Column([
        ft.TextButton("←  Kembali ke transaksi", on_click=on_cancel),
        title("Imbas resit", size=27),
        label("Halakan kamera ke resit atau tangkap skrin pembelian anda.", color=MUTED),
        card(ft.Column([camera, status], spacing=10), padding=10),
        card(ft.Row([
            ft.Icon(ft.Icons.INFO_OUTLINE, color=PRIMARY),
            label("Selepas mengambil gambar, semak butiran dan pilih kategori sebelum menyimpan.", size=12, color=MUTED),
        ], spacing=9), color=PURPLE_SOFT, padding=12),
        primary_button("Ambil gambar", on_capture, icon=ft.Icons.CAMERA_ALT),
    ], spacing=14, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)


__all__ = ["live", "review"]
