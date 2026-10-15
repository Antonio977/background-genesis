#!/usr/bin/env python3
"""Interfaccia grafica in stile KDE Plasma per crea_sfondi_qutec.py.

Avvio:
    python3 qutec_sfondi_gui.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from PySide6.QtCore import QTimer, QUrl, Qt
from PySide6.QtGui import QDesktopServices, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QRadioButton, QButtonGroup, QScrollArea,
    QSlider, QSplitter, QTabWidget, QVBoxLayout, QWidget,
)

import crea_sfondi_qutec as core

BASE_DIR = Path(__file__).resolve().parent
FONTS_DIR = BASE_DIR / "fonts"

COLORS = {"Bianco": "#FFFFFF", "Nero": "#000000"}


def pil_to_pixmap(img):
    rgb = img.convert("RGB")
    w, h = rgb.size
    data = rgb.tobytes()
    qimg = QImage(data, w, h, 3 * w, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


def fitted_font_box(draw, text, path, max_w, max_h):
    low, high = 1, max(2, int(max_w))
    while low < high:
        size = (low + high + 1) // 2
        font = ImageFont.truetype(path, size)
        box = draw.textbbox((0, 0), text, font=font)
        if box[2] - box[0] <= max_w and box[3] - box[1] <= max_h:
            low = size
        else:
            high = size - 1
    return ImageFont.truetype(path, low)


def render_pair(background, text, font_file, color, p):
    w, h = background.size
    measure = ImageDraw.Draw(background)
    center_font = fitted_font_box(
        measure, text, font_file, w * p["center_w"], h * p["center_h"])
    corner_font = fitted_font_box(
        measure, text, font_file, w * p["corner_w"], h * p["corner_h"])

    cbox = measure.textbbox((0, 0), text, font=center_font)
    tw, th = cbox[2] - cbox[0], cbox[3] - cbox[1]
    cx = (w - tw) // 2 - cbox[0]
    cy = (h - th) // 2 - cbox[1] + int(h * p["center_y"])
    cy = max(0, min(cy, h - th))

    kbox = measure.textbbox((0, 0), text, font=corner_font)
    kh = kbox[3] - kbox[1]
    kx = int(w * p["margin"]) - kbox[0]
    ky = h - int(h * p["bottom"]) - kh - kbox[1]
    ky = max(0, min(ky, h - kh))

    out_center = background.copy()
    ImageDraw.Draw(out_center).text((cx, cy), text, font=center_font, fill=color)
    out_corner = background.copy()
    ImageDraw.Draw(out_corner).text((kx, ky), text, font=corner_font, fill=color)
    return out_center, out_corner


class QuotaRow(QWidget):
    def __init__(self, minimum, maximum, value, step=0.005, parent=None):
        super().__init__(parent)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(round(minimum * 1000), round(maximum * 1000))
        self.slider.setValue(round(value * 1000))
        self.spin = QDoubleSpinBox()
        self.spin.setRange(minimum, maximum)
        self.spin.setSingleStep(step)
        self.spin.setDecimals(3)
        self.spin.setValue(value)
        self.spin.setFixedWidth(90)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.slider, 1)
        lay.addWidget(self.spin)
        self.slider.valueChanged.connect(
            lambda v: self.spin.setValue(v / 1000.0))
        self.spin.valueChanged.connect(
            lambda v: self.slider.setValue(round(v * 1000)))

    def value(self):
        return self.spin.value()

    def setValue(self, v):
        self.spin.setValue(v)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Background Genesis")
        self.setWindowIcon(QIcon.fromTheme("preferences-desktop-wallpaper"))
        self.resize(1180, 720)
        self.image_path = None
        self._preview_cache = None
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(180)
        self._debounce.timeout.connect(self.update_preview)
        self._build_ui()
        self._collect_defaults()
        self._refresh_preview_soon()

    def _build_ui(self):
        header = QLabel("Background Genesis")
        header.setStyleSheet(
            "font-size: 30px; font-weight: 800; color: #ff7040;")
        sub = QLabel("Scegli foto, font, colore e dimensioni del logo · anteprima live")
        sub.setStyleSheet("color: palette(mid);")

        # ---- controlli a sinistra ----
        controls = QWidget()
        form = QVBoxLayout(controls)
        form.setSpacing(12)

        g_img = QGroupBox("Immagine")
        li = QVBoxLayout(g_img)
        row = QHBoxLayout()
        self.edit_image = QLineEdit()
        self.edit_image.setPlaceholderText("Seleziona una foto…")
        self.edit_image.setReadOnly(True)
        btn_browse = QPushButton(QIcon.fromTheme("document-open"), "Sfoglia…")
        btn_browse.clicked.connect(self.pick_image)
        row.addWidget(self.edit_image, 1)
        row.addWidget(btn_browse)
        li.addLayout(row)
        self.lbl_info = QLabel("Nessuna immagine selezionata.")
        self.lbl_info.setStyleSheet("color: palette(mid); font-size: 12px;")
        li.addWidget(self.lbl_info)
        form.addWidget(g_img)

        g_logo = QGroupBox("Logo")
        fl = QFormLayout(g_logo)
        self.edit_text = QLineEdit("QuTec")
        self.edit_text.textChanged.connect(self._refresh_preview_soon)
        fl.addRow("Testo:", self.edit_text)
        self.combo_font = QComboBox()
        self._fill_fonts()
        self.combo_font.currentIndexChanged.connect(self._on_font_changed)
        fl.addRow("Font:", self.combo_font)
        color_row = QWidget()
        cl = QHBoxLayout(color_row)
        cl.setContentsMargins(0, 0, 0, 0)
        self.radio_white = QRadioButton("Bianco")
        self.radio_black = QRadioButton("Nero")
        self.radio_both = QRadioButton("Entrambi")
        self.radio_white.setChecked(True)
        self.radio_white.setIcon(QIcon.fromTheme("fill-color-white"))
        self.radio_black.setIcon(QIcon.fromTheme("fill-color-black"))
        group = QButtonGroup(self)
        for r in (self.radio_white, self.radio_black, self.radio_both):
            group.addButton(r)
            cl.addWidget(r)
            r.toggled.connect(self._refresh_preview_soon)
        fl.addRow("Colore:", color_row)
        form.addWidget(g_logo)

        g_center = QGroupBox("Logo centrale — dimensioni e altezza")
        fc = QFormLayout(g_center)
        self.q_center_w = QuotaRow(0.03, 0.35, 0.115)
        self.q_center_h = QuotaRow(0.02, 0.40, 0.12)
        self.q_center_y = QuotaRow(-0.25, 0.25, 0.0)
        for q in (self.q_center_w, self.q_center_h, self.q_center_y):
            q.slider.valueChanged.connect(self._refresh_preview_soon)
            q.spin.valueChanged.connect(self._refresh_preview_soon)
        fc.addRow("Larghezza max (×W):", self.q_center_w)
        fc.addRow("Altezza max (×H):", self.q_center_h)
        fc.addRow("Spost. verticale (±×H):", self.q_center_y)
        form.addWidget(g_center)

        g_corner = QGroupBox("Logo in basso a sinistra — dimensioni e altezza")
        fk = QFormLayout(g_corner)
        self.q_corner_w = QuotaRow(0.02, 0.20, 0.055)
        self.q_corner_h = QuotaRow(0.015, 0.25, 0.06)
        self.q_margin = QuotaRow(0.0, 0.30, 0.055)
        self.q_bottom = QuotaRow(0.02, 0.40, 0.15)
        for q in (self.q_corner_w, self.q_corner_h, self.q_margin, self.q_bottom):
            q.slider.valueChanged.connect(self._refresh_preview_soon)
            q.spin.valueChanged.connect(self._refresh_preview_soon)
        fk.addRow("Larghezza max (×W):", self.q_corner_w)
        fk.addRow("Altezza max (×H):", self.q_corner_h)
        fk.addRow("Margine laterale (×W):", self.q_margin)
        fk.addRow("Distanza dal basso (×H):", self.q_bottom)
        form.addWidget(g_corner)

        btn_row = QHBoxLayout()
        self.btn_reset = QPushButton(QIcon.fromTheme("view-refresh"), "Default")
        self.btn_reset.clicked.connect(self.reset_defaults)
        self.btn_folder = QPushButton(QIcon.fromTheme("folder-open"), "Apri cartella")
        self.btn_folder.setEnabled(False)
        self.btn_folder.clicked.connect(self.open_folder)
        self.btn_go = QPushButton(QIcon.fromTheme("media-playback-start"), "Genera sfondi")
        self.btn_go.setDefault(True)
        self.btn_go.setStyleSheet(
            "QPushButton { font-weight: 700; padding: 8px 18px; }")
        self.btn_go.clicked.connect(self.generate)
        btn_row.addWidget(self.btn_reset)
        btn_row.addWidget(self.btn_folder)
        btn_row.addWidget(self.btn_go, 1)
        form.addLayout(btn_row)
        form.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(controls)
        scroll.setFixedWidth(440)

        # ---- destra: anteprima + log ----
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.addWidget(header)
        rl.addWidget(sub)
        self.tabs = QTabWidget()
        self.view_center = QLabel("Nessuna anteprima")
        self.view_center.setAlignment(Qt.AlignCenter)
        self.view_center.setMinimumSize(480, 270)
        self.view_center.setStyleSheet(
            "background: palette(base); border-radius: 8px;")
        self.view_corner = QLabel("Nessuna anteprima")
        self.view_corner.setAlignment(Qt.AlignCenter)
        self.view_corner.setMinimumSize(480, 270)
        self.view_corner.setStyleSheet(
            "background: palette(base); border-radius: 8px;")
        self.tabs.addTab(self.view_center, QIcon.fromTheme("view-center"), "Centrato")
        self.tabs.addTab(self.view_corner, QIcon.fromTheme("go-bottom"), "Basso a sinistra")
        rl.addWidget(self.tabs, 1)
        rl.addWidget(QLabel("Registro:"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(200)
        self.log.setFixedHeight(130)
        rl.addWidget(self.log)

        split = QSplitter()
        split.addWidget(scroll)
        split.addWidget(right)
        split.setStretchFactor(1, 1)
        self.setCentralWidget(split)

    def _fill_fonts(self):
        self._font_files = {}
        if FONTS_DIR.is_dir():
            for f in sorted(FONTS_DIR.glob("*.ttf")) + sorted(FONTS_DIR.glob("*.otf")):
                label = f.stem.replace("-", " ")
                self.combo_font.addItem(QIcon.fromTheme("font"), label, str(f))
                self._font_files[label] = f
        self.combo_font.addItem(QIcon.fromTheme("system"), "Sistema (fallback)", "")
        self.combo_font.addItem(QIcon.fromTheme("document-open"), "Scegli file…", "__custom__")
        for i in range(self.combo_font.count()):
            if "Space Grotesk" in self.combo_font.itemText(i) or "SpaceGrotesk" in str(self.combo_font.itemData(i)):
                self.combo_font.setCurrentIndex(i)
                break

    def _collect_defaults(self):
        self._defaults = self.params()

    def _on_font_changed(self, *args):
        if self.combo_font.itemData(self.combo_font.currentIndex()) == "__custom__":
            path, _ = QFileDialog.getOpenFileName(
                self, "Seleziona font",
                str(FONTS_DIR),
                "Font (*.ttf *.otf *.woff *.woff2);;Tutti i file (*)")
            if path:
                self._custom_font = path
                self.combo_font.setItemData(
                    self.combo_font.currentIndex(), path)
            else:
                self.combo_font.setCurrentIndex(0)
                return
        self._refresh_preview_soon()

    def params(self):
        idx = self.combo_font.currentIndex()
        data = self.combo_font.itemData(idx)
        if data == "__custom__":
            data = getattr(self, "_custom_font", "")
        return {
            "text": self.edit_text.text() or "QuTec",
            "font_sel": data,
            "center_w": self.q_center_w.value(),
            "center_h": self.q_center_h.value(),
            "center_y": self.q_center_y.value(),
            "corner_w": self.q_corner_w.value(),
            "corner_h": self.q_corner_h.value(),
            "margin": self.q_margin.value(),
            "bottom": self.q_bottom.value(),
        }

    def reset_defaults(self):
        d = self._defaults
        self.edit_text.setText(d["text"])
        self.q_center_w.setValue(d["center_w"])
        self.q_center_h.setValue(d["center_h"])
        self.q_center_y.setValue(d["center_y"])
        self.q_corner_w.setValue(d["corner_w"])
        self.q_corner_h.setValue(d["corner_h"])
        self.q_margin.setValue(d["margin"])
        self.q_bottom.setValue(d["bottom"])
        self.radio_white.setChecked(True)

    # ---- immagine / font ----
    def pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleziona foto",
            str(BASE_DIR),
            "Immagini (*.jpg *.jpeg *.png *.webp *.avif *.bmp);;Tutti i file (*)")
        if path:
            self.set_image(Path(path))

    def set_image(self, path):
        try:
            with Image.open(path) as im:
                im.verify()
            with Image.open(path) as im:
                size = im.size
        except Exception as exc:
            QMessageBox.warning(self, "Immagine non valida", str(exc))
            return
        self.image_path = Path(path)
        self.edit_image.setText(str(path))
        self.lbl_info.setText(f"{path.name} · {size[0]}×{size[1]} px")
        self._preview_cache = None
        self.update_preview()

    def resolve_font(self):
        data = self.params()["font_sel"]
        if data:
            p = Path(data)
            if p.is_file():
                return p
        try:
            return core.font_path(None)
        except FileNotFoundError as exc:
            QMessageBox.warning(self, "Font mancante", str(exc))
            return None

    def selected_colors(self):
        if self.radio_both.isChecked():
            return [COLORS["Bianco"], COLORS["Nero"]]
        if self.radio_black.isChecked():
            return [COLORS["Nero"]]
        return [COLORS["Bianco"]]

    # ---- anteprima ----
    def _refresh_preview_soon(self, *args):
        self._debounce.start()

    def _pil_to_pixmap(self, img, max_w=960):
        thumb = img.copy()
        thumb.thumbnail((max_w, max_w * 9 // 16), Image.LANCZOS)
        return pil_to_pixmap(thumb)

    def update_preview(self):
        if self.image_path is None:
            return
        font_file = self.resolve_font()
        if font_file is None:
            return
        try:
            with Image.open(self.image_path) as src:
                bg = src.convert("RGB")
        except Exception as exc:
            self.log.appendPlainText(f"Errore anteprima: {exc}")
            return
        colors = self.selected_colors()
        color = colors[0]
        p = self.params()
        small = bg.copy()
        small.thumbnail((960, 540), Image.LANCZOS)
        try:
            c_prev, k_prev = render_pair(small, p["text"], font_file, color, p)
        except Exception as exc:
            self.log.appendPlainText(f"Errore anteprima: {exc}")
            return
        for view, img in ((self.view_center, c_prev), (self.view_corner, k_prev)):
            pix = pil_to_pixmap(img)
            avail = view.size()
            if avail.width() > 10 and avail.height() > 10:
                view.setPixmap(pix.scaled(
                    avail * 0.98, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                view.setPixmap(pix.scaledToWidth(960, Qt.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_preview_soon()

    # ---- generazione ----
    def generate(self):
        if self.image_path is None:
            QMessageBox.information(
                self, "Manca la foto", "Seleziona prima una foto con «Sfoglia…».")
            return
        font_file = self.resolve_font()
        if font_file is None:
            return
        p = self.params()
        try:
            with Image.open(self.image_path) as src:
                bg = src.convert("RGB")
        except Exception as exc:
            QMessageBox.warning(self, "Errore", f"Impossibile aprire l'immagine:\n{exc}")
            return
        stem = self.image_path.with_suffix("")
        made = []
        for color in self.selected_colors():
            suffix = ""
            if len(self.selected_colors()) > 1:
                suffix = "_bianco" if color == COLORS["Bianco"] else "_nero"
            c_img, k_img = render_pair(bg, p["text"], font_file, color, p)
            c_out = stem.with_name(f"{stem.name}{suffix}_qutec_centro.jpg")
            k_out = stem.with_name(f"{stem.name}{suffix}_qutec_basso_sinistra.jpg")
            c_img.save(c_out, quality=95, subsampling=0)
            k_img.save(k_out, quality=95, subsampling=0)
            made += [c_out, k_out]
            self.log.appendPlainText(f"Creato: {c_out.name}")
            self.log.appendPlainText(f"Creato: {k_out.name}")
        self._last_outputs = made
        self.btn_folder.setEnabled(True)
        self.log.appendPlainText(
            f"Font: {font_file} · testo «{p['text']}» · "
            f"centro W={p['center_w']:.3f} H={p['center_h']:.3f} Y={p['center_y']:+.3f} · "
            f"basso W={p['corner_w']:.3f} H={p['corner_h']:.3f}")
        QMessageBox.information(
            self, "Sfondi creati",
            "\n".join(f"• {m.name}" for m in made))

    def open_folder(self):
        outs = getattr(self, "_last_outputs", [])
        target = outs[0].parent if outs else BASE_DIR
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))


def main():
    app = QApplication(sys.argv)
    QApplication.setOrganizationName("QUTEC")
    QApplication.setApplicationName("Background Genesis")
    win = MainWindow()
    if len(sys.argv) > 1 and Path(sys.argv[1]).is_file():
        win.set_image(Path(sys.argv[1]))
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
