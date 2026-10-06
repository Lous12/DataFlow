from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QPushButton,
    QWidget,
)

from core.readers import is_supported_file


OPERATORS = [
    ("Равно", "equals"),
    ("Не равно", "not_equals"),
    ("Содержит", "contains"),
    ("Не содержит", "not_contains"),
    ("Начинается с", "starts_with"),
    ("Заканчивается на", "ends_with"),
    (">", "gt"),
    (">=", "gte"),
    ("<", "lt"),
    ("<=", "lte"),
    ("Одно из (;)", "one_of"),
    ("Пусто", "empty"),
    ("Не пусто", "not_empty"),
]


class FileDropList(QListWidget):
    files_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        paths = []
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.is_file() and is_supported_file(path):
                paths.append(str(path))

        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
        else:
            event.ignore()


class FilterRow(QWidget):
    remove_requested = Signal(object)

    def __init__(self, columns: list[str] | None = None) -> None:
        super().__init__()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.enabled = QCheckBox()
        self.enabled.setChecked(True)
        self.enabled.setToolTip("Включить/выключить правило")

        self.column = QComboBox()
        self.column.setMinimumWidth(150)

        self.operator = QComboBox()
        self.operator.setMinimumWidth(140)
        for label, code in OPERATORS:
            self.operator.addItem(label, code)

        self.value = QLineEdit()
        self.value.setPlaceholderText("Значение")
        self.value.setMinimumWidth(150)

        self.remove_button = QPushButton("✕")
        self.remove_button.setFixedWidth(34)
        self.remove_button.clicked.connect(
            lambda: self.remove_requested.emit(self)
        )

        self.operator.currentIndexChanged.connect(
            self._sync_value_enabled
        )

        layout.addWidget(self.enabled)
        layout.addWidget(self.column, 2)
        layout.addWidget(self.operator, 2)
        layout.addWidget(self.value, 2)
        layout.addWidget(self.remove_button)

        self.set_columns(columns or [])
        self._sync_value_enabled()

    def set_columns(self, columns: list[str]) -> None:
        current = self.column.currentText()
        self.column.clear()
        self.column.addItems(columns)

        if current in columns:
            self.column.setCurrentText(current)

    def _sync_value_enabled(self) -> None:
        no_value = self.operator.currentData() in {"empty", "not_empty"}
        self.value.setEnabled(not no_value)
        if no_value:
            self.value.clear()
