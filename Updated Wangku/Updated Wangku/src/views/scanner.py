import flet as ft

from theme import CORAL, CORAL_SOFT, INK, MINT, MUTED, PRIMARY, PURPLE_SOFT, card, label, primary_button, title


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


def review(photo, description, amount, category, message, on_save, on_retake, on_cancel):
    return ft.Column([
        ft.TextButton("←  Kembali ke transaksi", on_click=on_cancel),
        title("Semak pembelian anda", size=27),
        label("Semak gambar dan isi butiran. Bacaan resit automatik akan ditambah bersama perkhidmatan analisis.", color=MUTED),
        card(ft.Image(src=photo, height=185, fit=ft.BoxFit.CONTAIN, border_radius=16), color=ft.Colors.WHITE, padding=10),
        ft.Container(content=ft.Row([
            ft.Icon(ft.Icons.EDIT_NOTE, color=CORAL),
            label("Gambar berjaya diambil. Sila isi atau betulkan butiran di bawah.", size=12, color=CORAL),
        ], spacing=8), bgcolor=CORAL_SOFT, padding=12, border_radius=16),
        description,
        amount,
        category,
        message,
        ft.Row([
            ft.OutlinedButton(content=ft.Text("Ambil semula"), icon=ft.Icons.CAMERA_ALT, on_click=on_retake),
            ft.Container(expand=True),
            primary_button("Tambah transaksi", on_save, icon=ft.Icons.CHECK),
        ], wrap=True, spacing=8),
    ], spacing=13, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
