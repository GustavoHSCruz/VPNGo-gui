"""Add-app, add-profile and password dialogs."""

import re
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QVBoxLayout)

from . import theme
from .i18n import tr


APP_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_. -]{0,79}")
PROFILE_NAME = re.compile(r"[a-z][a-z0-9_-]{0,31}")


def app_key(path):
    """The name vpngo gives an executable: its file name without .exe/.app, case-folded."""
    name = Path(path).name
    name = re.sub(r"\.(?:exe|app)$", "", name, flags=re.I)
    return name.casefold() if APP_NAME.fullmatch(name) else None


def profile_from_file(path):
    stem = re.sub(r"[^a-z0-9_-]+", "-", Path(path).stem.casefold()).strip("-_")
    stem = re.sub(r"^[^a-z]+", "", stem)[:32]
    return stem


class Dialog(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(24, 22, 24, 20)
        self.layout_.setSpacing(0)
        heading = QLabel(title)
        heading.setFont(theme.font(18, QFont.Weight.DemiBold))
        self.layout_.addWidget(heading)
        self.layout_.addSpacing(14)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet(f"color: {theme.DANGER}; font-size: 13px;")
        self.error.hide()

    def field(self, label, widget):
        caption = QLabel(label)
        caption.setProperty("role", "field")
        # A file row is a layout; its line edit is the field the caption names.
        caption.setBuddy(widget.itemAt(0).widget() if isinstance(widget, QHBoxLayout) else widget)
        self.layout_.addSpacing(10)
        self.layout_.addWidget(caption)
        self.layout_.addSpacing(6)
        if isinstance(widget, QHBoxLayout):
            self.layout_.addLayout(widget)
        else:
            self.layout_.addWidget(widget)

    def buttons(self, confirm):
        self.layout_.addSpacing(10)
        self.layout_.addWidget(self.error)
        self.layout_.addSpacing(18)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addStretch()
        cancel = QPushButton(tr("cancel"))
        cancel.clicked.connect(self.reject)
        self.confirm = QPushButton(confirm)
        self.confirm.setProperty("primary", True)
        self.confirm.setDefault(True)
        self.confirm.clicked.connect(self.submit)
        for button in (cancel, self.confirm):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            row.addWidget(button)
        self.layout_.addLayout(row)

    def file_row(self, line, caption, file_filter=""):
        row = QHBoxLayout()
        row.setSpacing(8)
        line.setProperty("mono", True)
        row.addWidget(line, 1)
        choose = QPushButton(tr("choose"))
        choose.setCursor(Qt.CursorShape.PointingHandCursor)
        choose.clicked.connect(lambda: self._pick(line, caption, file_filter))
        row.addWidget(choose)
        return row

    def _pick(self, line, caption, file_filter):
        path, _ = QFileDialog.getOpenFileName(self, caption, line.text() or str(Path.home()), file_filter)
        if path:
            line.setText(path)

    def fail(self, text):
        self.error.setText(text)
        self.error.show()

    def submit(self):
        self.accept()


class AddAppDialog(Dialog):
    def __init__(self, profiles, parent=None):
        super().__init__(tr("add_app_title"), parent)
        self.path = QLineEdit()
        self.path.setPlaceholderText("/usr/bin/firefox")
        self.field(tr("app_file"), self.file_row(self.path, tr("app_file")))
        self.profile = QComboBox()
        self.profile.addItems(profiles)
        self.profile.setFont(theme.font(13, mono=True))
        self.field(tr("profile"), self.profile)
        self.layout_.addSpacing(14)
        self.start_now = QCheckBox(tr("start_now"))
        self.layout_.addWidget(self.start_now)
        self.buttons(tr("add"))

    def submit(self):
        path = self.path.text().strip()
        if not path or not Path(path).expanduser().exists():
            return self.fail(tr("file_missing"))
        if not app_key(path):
            return self.fail(tr("bad_app_name"))
        self.accept()

    def values(self):
        path = str(Path(self.path.text().strip()).expanduser())
        return path, app_key(path), self.profile.currentText(), self.start_now.isChecked()


class AddProfileDialog(Dialog):
    def __init__(self, existing=(), parent=None):
        super().__init__(tr("add_profile_title"), parent)
        self.existing = set(existing)
        self.path = QLineEdit()
        self.path.setPlaceholderText("~/Downloads/br-01.conf")
        self.path.textChanged.connect(self._suggest_name)
        self.field(tr("profile_file"), self.file_row(self.path, tr("profile_file"), tr("conf_filter")))
        self.name = QLineEdit()
        self.name.setProperty("mono", True)
        self.name.setPlaceholderText("br")
        self.name.setMaxLength(32)
        self.field(tr("profile_name"), self.name)
        self.named_by_user = False
        self.name.textEdited.connect(lambda: setattr(self, "named_by_user", True))
        self.buttons(tr("add"))

    def _suggest_name(self, path):
        if not self.named_by_user:
            self.name.setText(profile_from_file(path))

    def submit(self):
        path = Path(self.path.text().strip()).expanduser()
        if not self.path.text().strip() or not path.is_file():
            return self.fail(tr("file_missing"))
        name = self.name.text().strip().casefold()
        if not PROFILE_NAME.fullmatch(name):
            return self.fail(tr("bad_profile_name"))
        if name in self.existing:
            return self.fail(tr("profile_exists"))
        self.accept()

    def values(self):
        return self.name.text().strip().casefold(), str(Path(self.path.text().strip()).expanduser())


class _Checked(QObject):
    done = Signal(bool)


class PasswordDialog(Dialog):
    """Asks for the sudo password and checks it with sudo before vpngo receives it."""

    def __init__(self, action_text, check, parent=None):
        super().__init__(tr("password_title"), parent)
        self.check = check
        body = QLabel(tr("password_body", action=action_text))
        body.setWordWrap(True)
        body.setProperty("role", "muted")
        self.layout_.addWidget(body)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.field(tr("password_label"), self.password)
        self.buttons(tr("continue"))
        self.result_password = None
        self.signals = _Checked()
        self.signals.done.connect(self._checked)
        self.password.setFocus()

    def submit(self):
        value = self.password.text()
        if not value:
            return
        self.confirm.setEnabled(False)
        self.password.setEnabled(False)
        self.error.hide()
        threading.Thread(target=lambda: self.signals.done.emit(self.check(value)), daemon=True).start()

    def _checked(self, valid):
        if valid:
            self.result_password = self.password.text()
            self.password.clear()
            self.accept()
            return
        self.confirm.setEnabled(True)
        self.password.setEnabled(True)
        self.password.selectAll()
        self.password.setFocus()
        self.fail(tr("wrong_password"))
