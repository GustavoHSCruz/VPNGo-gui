"""VPNGo Setup's window, in the interface's own look: one choice, the steps as they run, the end."""

import subprocess

from PySide6.QtCore import QObject, QPointF, QRectF, QSize, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QAbstractButton, QCheckBox, QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar,
                               QPushButton, QStackedWidget, QVBoxLayout, QWidget)

import installer
from strings import tr
from vpngo_gui import theme
from vpngo_gui.widgets import StateDot


def label(text, size=14, weight=QFont.Weight.Normal, color=theme.TEXT, wrap=True):
    result = QLabel(text)
    result.setFont(theme.font(size, weight))
    result.setStyleSheet(f"color: {color};")
    result.setWordWrap(wrap)
    return result


def button(text, primary=False, danger=False):
    result = QPushButton(text)
    result.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary:
        result.setProperty("primary", True)
    if danger:
        result.setStyleSheet(f"QPushButton {{ background: {theme.DANGER}; border-color: {theme.DANGER}; "
                             f"color: {theme.BG}; font-weight: 600; }}")
    return result


class OptionCard(QAbstractButton):
    """One of the two install choices: a surface card that lights its border and dot when chosen."""

    def __init__(self, title, detail, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(title)
        self.title, self.detail = title, detail
        self.setFixedHeight(84)

    def sizeHint(self):
        return QSize(460, 84)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        chosen = self.isChecked()
        border = theme.mix(theme.FAINT, theme.VPN, .6 if chosen else (.3 if self.underMouse() or self.hasFocus() else 0))
        painter.setPen(QPen(border, 1))
        painter.setBrush(QColor(theme.SURFACE))
        painter.drawRoundedRect(rect, 12, 12)
        # The radio dot, like the interface's state dot.
        center = rect.topLeft() + QRectF(0, 0, 36, 36).center() + QRectF(0, 0, 4, 6).bottomRight()
        if chosen:
            halo = QColor(theme.VPN)
            halo.setAlphaF(.22)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(halo)
            painter.drawEllipse(center, 6.5, 6.5)
            painter.setBrush(QColor(theme.VPN))
            painter.drawEllipse(center, 3.5, 3.5)
        else:
            painter.setPen(QPen(theme.mix(theme.FAINT, theme.MUTED, .35), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, 5, 5)
        text = rect.adjusted(44, 14, -16, -12)
        painter.setPen(QColor(theme.TEXT))
        painter.setFont(theme.font(14, QFont.Weight.DemiBold))
        painter.drawText(text, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self.title)
        painter.setPen(QColor(theme.MUTED))
        painter.setFont(theme.font(13))
        painter.drawText(text.adjusted(0, 22, 0, 0), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, self.detail)

    def enterEvent(self, event):
        self.update()

    def leaveEvent(self, event):
        self.update()


class ResultMark(QWidget):
    """The end of a run: a check on green, a dash on amber or a cross on coral, in a soft halo."""

    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(44, 44)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor({"done": theme.VPN, "partial": theme.WARN}.get(self.kind, theme.DANGER))
        halo = QColor(color)
        halo.setAlphaF(.16)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(halo)
        painter.drawEllipse(QRectF(0, 0, 44, 44))
        painter.setBrush(color)
        painter.drawEllipse(QRectF(10, 10, 24, 24))
        pen = QPen(QColor(theme.BG), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        if self.kind == "done":
            painter.drawPolyline([QPointF(16.5, 22.5), QPointF(20.5, 26.5), QPointF(27.5, 18.5)])
        elif self.kind == "partial":
            painter.drawLine(QPointF(17, 22), QPointF(27, 22))
        else:
            painter.drawLine(QPointF(18, 18), QPointF(26, 26))
            painter.drawLine(QPointF(26, 18), QPointF(18, 26))


class StepRow(QWidget):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.dot = StateDot()
        self.dot.set_state(theme.MUTED, hollow=True, animate=False)
        self.text = label(text, 14, color=theme.MUTED, wrap=False)
        self.detail = label("", 12, color=theme.MUTED, wrap=False)
        self.detail.setFont(theme.font(12, mono=True))
        layout.addWidget(self.dot)
        layout.addWidget(self.text, 1)
        layout.addWidget(self.detail)

    def set_state(self, state, animate=True):
        self.dot.set_busy(state == "running")
        colors = {"running": theme.VPN, "done": theme.VPN, "failed": theme.DANGER}
        self.dot.set_state(colors.get(state, theme.MUTED), hollow=state not in colors, animate=animate)
        self.text.setStyleSheet(f"color: {theme.TEXT if state in colors else theme.MUTED};")
        if state != "running":
            self.detail.setText("")


class Worker(QObject, installer.Events):
    """Runs an install or uninstall off the window's thread and reports through signals."""

    stepped = Signal(str, str)
    progressed = Signal(str, float)
    logged = Signal(str)
    finished = Signal(int, str)

    def __init__(self, action, **options):
        QObject.__init__(self)
        self.action, self.options = action, options

    def step(self, name, state):
        self.stepped.emit(name, state)

    def progress(self, name, fraction):
        self.progressed.emit(name, fraction)

    def log(self, line):
        self.logged.emit(line)

    def run(self):
        try:
            if self.action == "uninstall":
                installer.uninstall(self.log)
            else:
                installer.install(events=self, **self.options)
            self.finished.emit(0, "")
        except installer.SetupError as error:
            self.finished.emit(error.code, str(error))


class SetupWindow(QWidget):
    def __init__(self, uninstall=False, setup_exe=None):
        super().__init__()
        self.setup_exe = setup_exe
        self.exit_code = 0
        self.thread = self.worker = None
        self.setWindowTitle(tr("window"))
        self.setWindowIcon(QIcon(str(theme.ASSETS / "vpngo.svg")))
        self.setFixedSize(560, 520)
        self.setAutoFillBackground(True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 26, 32, 26)
        outer.setSpacing(22)
        outer.addLayout(self._brand())
        self.pages = QStackedWidget()
        outer.addWidget(self.pages, 1)
        self.choose_page = self._choose_page()
        self.uninstall_page = self._uninstall_page()
        self.progress_page = QWidget()
        self.end_page = QWidget()
        for page in (self.choose_page, self.uninstall_page, self.progress_page, self.end_page):
            self.pages.addWidget(page)
        self.pages.setCurrentWidget(self.uninstall_page if uninstall else self.choose_page)

    # --- Pages -------------------------------------------------------------------------

    def _brand(self):
        row = QHBoxLayout()
        row.setSpacing(10)
        logo = QLabel()
        renderer = QSvgRenderer(str(theme.ASSETS / "vpngo.svg"))
        pixmap = QPixmap(56, 56)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        pixmap.setDevicePixelRatio(2)
        logo.setPixmap(pixmap)
        row.addWidget(logo)
        name = label("VPNGo", 15, QFont.Weight.DemiBold, wrap=False)
        row.addWidget(name)
        row.addStretch(1)
        return row

    def _choose_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        try:
            previous = installer.installed_mode()
        except (ImportError, OSError):
            previous = None
        layout.addWidget(label(tr("upgrade_title" if previous else "install_title"), 20, QFont.Weight.DemiBold))
        layout.addSpacing(6)
        layout.addWidget(label(tr("install_body"), 14, color=theme.MUTED))
        layout.addSpacing(18)
        self.gui_card = OptionCard(tr("gui"), tr("gui_detail"))
        self.cli_card = OptionCard(tr("cli"), tr("cli_detail"))
        (self.cli_card if previous == "cli" else self.gui_card).setChecked(True)
        layout.addWidget(self.gui_card)
        layout.addSpacing(10)
        layout.addWidget(self.cli_card)
        layout.addSpacing(20)
        self.proxifyre = QCheckBox(tr("proxifyre"))
        self.proxifyre.setFont(theme.font(14))
        self.proxifyre.setChecked(previous is None)
        layout.addWidget(self.proxifyre)
        hint = label(tr("proxifyre_detail"), 12, color=theme.MUTED)
        hint.setContentsMargins(26, 2, 0, 0)
        layout.addWidget(hint)
        layout.addStretch(1)
        footer = QHBoxLayout()
        license_link = QPushButton(tr("license"))
        license_link.setCursor(Qt.CursorShape.PointingHandCursor)
        license_link.setStyleSheet(f"QPushButton {{ border: 0; padding: 0; color: {theme.MUTED}; font-size: 12px; }}"
                                   f"QPushButton:hover {{ color: {theme.TEXT}; }}")
        license_link.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl(f"https://github.com/{installer.REPOSITORY}/blob/main/LICENSE")))
        footer.addWidget(license_link)
        footer.addStretch(1)
        cancel = button(tr("cancel"))
        cancel.clicked.connect(self.close)
        start = button(tr("upgrade" if previous else "install"), primary=True)
        start.setDefault(True)
        start.clicked.connect(self.start_install)
        footer.addWidget(cancel)
        footer.addSpacing(8)
        footer.addWidget(start)
        layout.addLayout(footer)
        return page

    def _uninstall_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(label(tr("uninstall_title"), 20, QFont.Weight.DemiBold))
        layout.addSpacing(6)
        layout.addWidget(label(tr("uninstall_body"), 14, color=theme.MUTED))
        layout.addStretch(1)
        footer = QHBoxLayout()
        footer.addStretch(1)
        cancel = button(tr("cancel"))
        cancel.clicked.connect(self.close)
        remove = button(tr("uninstall"), danger=True)
        remove.clicked.connect(self.start_uninstall)
        footer.addWidget(cancel)
        footer.addSpacing(8)
        footer.addWidget(remove)
        layout.addLayout(footer)
        return page

    def _show_progress(self, title, names):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(label(title, 20, QFont.Weight.DemiBold))
        layout.addSpacing(6)
        layout.addWidget(label(tr("progress_body"), 14, color=theme.MUTED))
        layout.addSpacing(18)
        self.rows = {}
        for name in names:
            row = StepRow(tr(f"step_{name}"))
            self.rows[name] = row
            layout.addWidget(row)
            layout.addSpacing(8)
        layout.addSpacing(8)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(4)
        self.bar.setRange(0, len(names) * 100)
        self.bar.setStyleSheet(f"QProgressBar {{ border: 0; border-radius: 2px; background: {theme.FAINT}; }}"
                               f"QProgressBar::chunk {{ border-radius: 2px; background: {theme.VPN}; }}")
        layout.addWidget(self.bar)
        layout.addSpacing(12)
        self.details_button = QPushButton(tr("details_show"))
        self.details_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.details_button.setStyleSheet(f"QPushButton {{ border: 0; padding: 0; color: {theme.MUTED}; "
                                          f"font-size: 12px; text-align: left; }}"
                                          f"QPushButton:hover {{ color: {theme.TEXT}; }}")
        self.details_button.clicked.connect(self.toggle_details)
        layout.addWidget(self.details_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setFont(theme.font(12, mono=True))
        self.details.setStyleSheet(f"QPlainTextEdit {{ background: {theme.SURFACE}; border: 1px solid {theme.FAINT}; "
                                   f"border-radius: 10px; padding: 6px; color: {theme.MUTED}; }}")
        self.details.hide()
        layout.addSpacing(8)
        layout.addWidget(self.details, 1)
        layout.addStretch(0 if self.details.isVisible() else 1)
        self.pages.removeWidget(self.progress_page)
        self.progress_page = page
        self.pages.addWidget(page)
        self.pages.setCurrentWidget(page)
        self.order = names

    def _show_end(self, kind, title, body, primary=None, secondary=None):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(ResultMark(kind))
        layout.addSpacing(14)
        layout.addWidget(label(title, 20, QFont.Weight.DemiBold))
        layout.addSpacing(6)
        layout.addWidget(label(body, 14, color=theme.MUTED))
        layout.addStretch(1)
        if self.details.toPlainText():
            layout.addWidget(self.details_button, 0, Qt.AlignmentFlag.AlignLeft)
            layout.addSpacing(8)
            layout.addWidget(self.details, 3)
        footer = QHBoxLayout()
        footer.addStretch(1)
        for text, action, is_primary in filter(None, (secondary, primary)):
            item = button(text, primary=is_primary)
            item.clicked.connect(action)
            footer.addSpacing(8)
            footer.addWidget(item)
            if is_primary:
                item.setDefault(True)
        layout.addSpacing(12)
        layout.addLayout(footer)
        self.pages.removeWidget(self.end_page)
        self.end_page = page
        self.pages.addWidget(page)
        self.pages.setCurrentWidget(page)

    # --- Running ------------------------------------------------------------------------

    def _run(self, worker):
        self.thread = QThread(self)
        self.worker = worker
        worker.moveToThread(self.thread)
        worker.stepped.connect(self.on_step)
        worker.progressed.connect(self.on_progress)
        worker.logged.connect(self.details.appendPlainText)
        worker.finished.connect(self.on_finished)
        worker.finished.connect(self.thread.quit)
        self.thread.started.connect(worker.run)
        self.thread.start()

    def start_install(self):
        self.gui = self.gui_card.isChecked()
        names = installer.steps(self.gui, self.proxifyre.isChecked())
        self._show_progress(tr("progress_title"), names)
        self._run(Worker("install", gui=self.gui, proxifyre=self.proxifyre.isChecked(), setup_exe=self.setup_exe))

    def start_uninstall(self):
        self.gui = False
        self._show_progress(tr("uninstalling_title"), [])
        self.bar.setRange(0, 0)
        self._run(Worker("uninstall"))

    def on_step(self, name, state):
        if name in self.rows:
            self.rows[name].set_state(state)
            if state in ("done", "failed"):
                self.bar.setValue((self.order.index(name) + 1) * 100)

    def on_progress(self, name, fraction):
        if name in self.rows:
            self.rows[name].detail.setText(f"{fraction:.0%}")
            self.bar.setValue(int((self.order.index(name) + fraction) * 100))

    def toggle_details(self):
        visible = not self.details.isVisible()
        self.details.setVisible(visible)
        self.details_button.setText(tr("details_hide" if visible else "details_show"))

    def on_finished(self, code, message):
        self.exit_code = code
        if not self.order:  # Uninstall.
            if code == 0:
                installer.remove_setup_copy()
                self._show_end("done", tr("uninstalled_title"), tr("uninstalled_body"), (tr("close"), self.close, True))
            else:
                self._show_end("failed", tr("failed_title"), message, (tr("close"), self.close, True))
            return
        if code == 0:
            body = tr("done_gui" if self.gui else "done_cli")
            primary = (tr("open"), self.open_gui, True) if self.gui else (tr("close"), self.close, True)
            secondary = (tr("close"), self.close, False) if self.gui else None
            self._show_end("done", tr("done_title"), body, primary, secondary)
        elif code in (installer.PROXIFYRE_FAILED, installer.GUI_FAILED):
            self._show_end("partial", tr("partial_title"), message, (tr("close"), self.close, True))
        else:
            self._show_end("failed", tr("failed_title"), message, (tr("retry"), self.retry, True),
                           (tr("close"), self.close, False))

    def retry(self):
        self.details.clear()
        self.pages.setCurrentWidget(self.choose_page)

    def open_gui(self):
        root = installer.gui_root()
        subprocess.Popen([str(root / "venv/Scripts/pythonw.exe"), str(root / "app/run.py")],
                         creationflags=installer.NO_WINDOW, close_fds=True)
        self.close()

    def closeEvent(self, event):
        if self.thread and self.thread.isRunning():
            event.ignore()  # Stopping halfway would leave a half-installed vpngo.
            return
        super().closeEvent(event)
