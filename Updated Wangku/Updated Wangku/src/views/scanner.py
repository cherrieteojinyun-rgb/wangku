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
    "food": "Makanan", "makanan": "Makanan",
    "transport": "Pengangkutan", "pengangkutan": "Pengangkutan",
    "fun": "Hiburan", "entertainment": "Hiburan", "hiburan": "Hiburan",
    "books": "Buku", "book": "Buku", "buku": "Buku",
    "other": "Lain-lain", "lain": "Lain-lain", "lain-lain": "Lain-lain",
}
_REVIEWS = {}
_SUBMITTED = set()


def _photo_key(photo):
    return str(photo or "")


def _image_payload(photo):
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
    return mimetypes.guess_type(path.name)[0] or "image/jpeg", base64.b64encode(path.read_bytes()).decode("ascii")


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
        raw_price = item.get("price", item.get("amount"))
        try:
            price = float(str(raw_price).replace(",", "").replace("RM", "").strip())
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


async def _analyze(photo, review):
    review["running"] = True
    review["status"] = "Menganalisis resit…"
    _update_status(review)
    try:
        mime_type, image_data = await asyncio.to_thread(_image_payload, photo)
        contents = [{
            "role": "user",
            "parts": [
                {"text": "Extract every purchased line item, its individual price and a category. Return only JSON exactly shaped as {\"items\":[{\"description\":\"item\",\"price\":0.00,\"category\":\"Food|Transport|Fun|Books|Other\"}]}. Use line-item prices, not receipt total. If unreadable or not a receipt return {\"items\":[]}. Never guess missing prices. No markdown or conversational text."},
                {"inlineData": {"mimeType": mime_type, "data": image_data}},
            ],
        }]
        response = await asyncio.to_thread(
            post_gemini,
            contents,
            system_instruction="You accurately extract receipt line items. Return valid JSON only. Do not invent item names or prices.",
        )
        items = _parse_items(response)
        if items:
            review["items"] = items
            review["status"] = f"{len(items)} item dikesan. Sila semak sebelum menghantar."
            _render_items(review)
        else:
            review["status"] = "Tidak dapat membaca item resit. Tambah item secara manual."
    except ChatTransportError as error:
        messages = {
            "missing_key": "Gagal: Tetapkan GEMINI_API_KEY untuk analisis resit.",
            "network": "Gagal: Sambungan rangkaian bermasalah. Tambah item secara manual.",
            "rate_limit": "Gagal: Had penggunaan AI dicapai. Tambah item secara manual.",
            "unauthorized": "Gagal: Kunci Gemini tidak sah. Tambah item secara manual.",
            "empty": "Tidak dapat membaca resit. Tambah item secara manual.",
        }
        review["status"] = messages.get(str(error), "Gagal: Analisis AI tidak tersedia. Tambah item secara manual.")
    except (ValueError, OSError, TypeError, json.JSONDecodeError):
        review["status"] = "Tidak dapat membaca resit atau jawapan AI tidak sah. Tambah item secara manual."
    except Exception:
        review["status"] = "Gagal: Ralat analisis berlaku. Tambah item secara manual."
    finally:
        review["running"] = False
        _update_status(review)


def _update_status(review):
    control = review.get("status_control")
    if control is None:
        return
    control.value = review["status"]
    control.color = PRIMARY if review["running"] else (
        CORAL if review["status"].startswith(("Gagal", "Tidak")) else MINT
    )
    progress = review.get("progress_control")
    if progress is not None:
        progress.visible = review["running"]
    try:
        control.page.update()
    except (AttributeError, RuntimeError):
        pass


def _make_item_controls(review):
    controls = []
    for index, item in enumerate(review["items"]):
        def changed(field, event, idx=index):
            review["items"][idx][field] = event.control.value

        def remove(_event, idx=index):
            if len(review["items"]) <= 1:
                return
            review["items"].pop(idx)
            _render_items(review)

        controls.append(card(ft.Column([
            ft.Row([
                ft.TextField(
                    value=item.get("description", ""), label="Nama item", hint_text="cth. Nasi ayam",
                    border_radius=12, expand=True,
                    on_change=lambda e, fn=changed: fn("description", e),
                ),
                ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, tooltip="Padam item", on_click=remove),
            ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.END),
            ft.Row([
                ft.TextField(
                    value=str(item.get("amount", "")), label="Harga (RM)", prefix=ft.Text("RM "),
                    keyboard_type=ft.KeyboardType.NUMBER, border_radius=12, expand=True,
                    on_change=lambda e, fn=changed: fn("amount", e),
                ),
                ft.Dropdown(
                    value=item.get("category", "Makanan"), label="Kategori",
                    options=[ft.DropdownOption(text=name) for name in _CATEGORY_LABELS],
                    border_radius=12, expand=True,
                    on_change=lambda e, fn=changed: fn("category", e),
                ),
            ], spacing=8),
        ], spacing=8, tight=True), padding=12))
    return controls


def _render_items(review):
    column = review.get("items_control")
    if column is None:
        return
    column.controls = _make_item_controls(review)
    try:
        column.page.update()
    except (AttributeError, RuntimeError):
        pass


def review(photo, description, amount, category, message, on_save, on_retake, on_cancel):
    key = _photo_key(photo)
    review_state = _REVIEWS.setdefault(key, {
        "items": [], "status": "Menunggu analisis resit…", "running": False, "started": False,
    })
    if not review_state["items"] and description is not None and (description.value or "").strip():
        review_state["items"] = [{
            "description": description.value or "",
            "amount": (amount.value or "") if amount is not None else "",
            "category": (category.value or "Makanan") if category is not None else "Makanan",
        }]

    review_state["status_control"] = ft.Text(review_state["status"], size=12, color=PRIMARY)
    review_state["progress_control"] = ft.ProgressRing(size=16, stroke_width=2, color=PRIMARY, visible=review_state["running"])
    review_state["items_control"] = ft.Column(spacing=10, tight=True)
    _render_items(review_state)

    def add_item(_event):
        review_state["items"].append({"description": "", "amount": "", "category": "Makanan"})
        _render_items(review_state)

    async def submit(_event=None):
        if key in _SUBMITTED:
            return
        transactions = []
        for item in review_state["items"]:
            name = (item.get("description") or "").strip()
            try:
                price = float(str(item.get("amount", "")).replace(",", "").replace("RM", "").strip())
            except (TypeError, ValueError):
                price = 0
            if not name or price <= 0:
                message.value = "Lengkapkan keterangan dan harga yang melebihi RM 0 untuk setiap item."
                try:
                    message.page.update()
                except (AttributeError, RuntimeError):
                    pass
                return
            transactions.append((name, price, item.get("category", "Makanan")))
        if not transactions:
            message.value = "Tambah sekurang-kurangnya satu item yang sah sebelum menghantar."
            try:
                message.page.update()
            except (AttributeError, RuntimeError):
                pass
            return

        _SUBMITTED.add(key)
        try:
            for name, price, item_category in transactions:
                description.value = name
                amount.value = str(price)
                category.value = item_category
                await on_save()
        except Exception:
            _SUBMITTED.discard(key)
            message.value = "Tidak dapat menyimpan semua item. Sila cuba lagi."
            try:
                message.page.update()
            except (AttributeError, RuntimeError):
                pass

    if not review_state["started"]:
        review_state["started"] = True
        review_state["task"] = asyncio.create_task(_analyze(photo, review_state))

    return ft.Column([
        card(ft.Image(src=photo, height=185, fit=ft.BoxFit.CONTAIN, border_radius=16), color=ft.Colors.WHITE, padding=10),
        ft.Row([
            ft.OutlinedButton(content=ft.Text("Ambil semula"), icon=ft.Icons.CAMERA_ALT, on_click=on_retake),
            ft.TextButton("← Kembali", on_click=on_cancel),
        ], spacing=8),
        card(ft.Row([review_state["progress_control"], review_state["status_control"]], spacing=8), color=PURPLE_SOFT, padding=12),
        review_state["items_control"],
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
