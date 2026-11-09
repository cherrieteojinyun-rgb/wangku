import flet as ft

from theme import CORAL, MINT, MUTED, PRIMARY, PURPLE_SOFT, card, label, primary_button, title


_CATEGORY_LABELS = ("Makanan", "Pengangkutan", "Hiburan", "Buku", "Lain-lain")


def _item_row(index, item, on_item_change, on_item_remove):
    return ft.Column([
        ft.Row([
            ft.TextField(
                value=item.get("description", ""),
                label="Nama item",
                hint_text="cth. Nasi ayam",
                border_radius=12,
                expand=True,
                on_change=lambda e, idx=index, field="description": on_item_change(idx, field, e.control.value),
            ),
            ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                tooltip="Padam item",
                on_click=lambda e, idx=index: on_item_remove(idx),
            ),
        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.END),
        ft.Row([
            ft.TextField(
                value=str(item.get("amount", "")),
                label="Harga (RM)",
                prefix=ft.Text("RM "),
                keyboard_type=ft.KeyboardType.NUMBER,
                border_radius=12,
                expand=True,
                on_change=lambda e, idx=index, field="amount": on_item_change(idx, field, e.control.value),
            ),
            ft.Dropdown(
                value=item.get("category", "Makanan"),
                label="Kategori",
                options=[ft.DropdownOption(text=name) for name in _CATEGORY_LABELS],
                border_radius=12,
                expand=True,
                on_change=lambda e, idx=index, field="category": on_item_change(idx, field, e.control.value),
            ),
        ], spacing=8),
    ], spacing=8, tight=True)


def review(photo, items, status_text, analysis_running, on_item_change, on_add_item, on_remove_item, on_submit, on_retake, on_cancel, message=None):
    item_controls = ft.Column([
        _item_row(index, item, on_item_change, on_remove_item)
        for index, item in enumerate(items or [])
    ], spacing=10, tight=True)
    status_value = status_text or "Sedia untuk semakan"
    status_color = PRIMARY if analysis_running else (CORAL if status_value.startswith(("Gagal", "Tidak", "Ralat")) else MINT)

    controls = [
        ft.TextButton("←  Kembali ke transaksi", on_click=on_cancel),
        title("Semak pembelian anda", size=27),
        label("Semak gambar dan setiap item. Anda boleh mengubah, menambah atau padam sebelum menghantar.", color=MUTED),
        card(ft.Image(src=photo, height=185, fit=ft.BoxFit.CONTAIN, border_radius=16), color=ft.Colors.WHITE, padding=10),
        ft.OutlinedButton(content=ft.Text("Ambil semula"), icon=ft.Icons.CAMERA_ALT, on_click=on_retake),
        card(
            ft.Row([
                ft.ProgressRing(size=16, stroke_width=2, color=PRIMARY, visible=analysis_running),
                ft.Text(status_value, size=12, color=status_color, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            color=PURPLE_SOFT,
            padding=12,
        ),
        item_controls,
        ft.Row([
            ft.OutlinedButton(content=ft.Text("Tambah item"), icon=ft.Icons.ADD, on_click=on_add_item),
        ], alignment=ft.MainAxisAlignment.START),
    ]
    if message is not None:
        controls.append(message)
    controls.append(ft.Row([
        primary_button("Hantar", on_submit, icon=ft.Icons.CHECK),
    ], alignment=ft.MainAxisAlignment.END))
    return ft.Column(controls, spacing=13, horizontal_alignment=ft.CrossAxisAlignment.STRETCH, tight=True)


def live(camera, status, on_capture, on_cancel):
    return ft.Column([
        ft.TextButton("←  Kembali ke transaksi", on_click=on_cancel),
        title("Imbas resit", size=27),
        label("Halakan kamera ke resit atau tangkap skrin pembelian anda.", color=MUTED),
        card(ft.Column([
            camera,
            status,
        ], spacing=10), padding=10),
        card(ft.Row([
            ft.Icon(ft.Icons.INFO_OUTLINE, color=PRIMARY),
            label("Selepas mengambil gambar, semak butiran dan pilih kategori sebelum menyimpan.", size=12, color=MUTED),
        ], spacing=9), color=PURPLE_SOFT, padding=12),
        primary_button("Ambil gambar", on_capture, icon=ft.Icons.CAMERA_ALT),
    ], spacing=14, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)


__all__ = ["live", "review"]
