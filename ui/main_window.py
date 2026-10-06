import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
from PySide6.QtCore import QObject, QThread, Signal, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.exporters import export_processed_tables
from core.models import ExportOptions, FilterRule, ProcessingOptions
from core.processing import collect_unique_values, process_file_set
from core.readers import read_columns, read_table
from ui.widgets import FileDropList, FilterRow


def open_in_file_manager(path: Path) -> None:
    target = str(path)
    if sys.platform.startswith("win"):
        os.startfile(target)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", target])
    else:
        subprocess.Popen(["xdg-open", target])


class ProcessingWorker(QObject):
    finished = Signal(object, object)
    failed = Signal(str)
    progress = Signal(int, str)

    def __init__(
        self,
        files: list[str],
        processing_options: ProcessingOptions,
        export_options: ExportOptions,
    ) -> None:
        super().__init__()
        self.files = files
        self.processing_options = processing_options
        self.export_options = export_options

    def run(self) -> None:
        try:
            self.progress.emit(15, "Читаю и обрабатываю файлы…")
            tables = process_file_set(
                self.files,
                self.processing_options,
            )

            total_rows = sum(len(item.dataframe) for item in tables)
            self.progress.emit(
                70,
                f"После обработки: {total_rows:,} строк",
            )

            paths = export_processed_tables(
                tables,
                self.export_options,
            )

            self.progress.emit(
                100,
                f"Создано файлов: {len(paths)}",
            )
            self.finished.emit(tables, paths)
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("DataFlow — фильтры и пакетный экспорт")
        self.resize(1320, 860)

        self.file_paths: list[str] = []
        self.columns: list[str] = []
        self.filter_rows: list[FilterRow] = []
        self.worker_thread: QThread | None = None
        self.worker: ProcessingWorker | None = None

        self._build_ui()
        self._apply_style()
        self.add_filter_row()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        title = QLabel("DataFlow")
        title.setObjectName("title")
        root.addWidget(title)

        subtitle = QLabel(
            "Фильтры по любым столбцам + создание нескольких файлов за один запуск"
        )
        subtitle.setObjectName("subtitle")
        root.addWidget(subtitle)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._files_panel())
        splitter.addWidget(self._settings_panel())
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        root.addWidget(splitter, 2)

        preview_group = QGroupBox("Предпросмотр")
        preview_layout = QVBoxLayout(preview_group)

        self.preview = QTableWidget()
        self.preview.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.preview.horizontalHeader().setSectionResizeMode(
            QHeaderView.Interactive
        )
        self.preview.horizontalHeader().setStretchLastSection(True)
        preview_layout.addWidget(self.preview)
        root.addWidget(preview_group, 2)

        bottom = QHBoxLayout()

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)

        self.run_button = QPushButton("Обработать")
        self.run_button.setObjectName("primaryButton")
        self.run_button.clicked.connect(self.start_processing)

        bottom.addWidget(self.progress, 1)
        bottom.addWidget(self.run_button)
        root.addLayout(bottom)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(105)
        self.log.setPlaceholderText("Здесь появится лог обработки…")
        root.addWidget(self.log)

    def _files_panel(self) -> QWidget:
        box = QGroupBox("1. Файлы")
        layout = QVBoxLayout(box)

        hint = QLabel(
            "Перетащите сюда XLSX / CSV / JSON\n"
            "Можно добавить сразу много файлов"
        )
        hint.setAlignment(Qt.AlignCenter)
        hint.setObjectName("dropHint")
        layout.addWidget(hint)

        self.file_list = FileDropList()
        self.file_list.files_dropped.connect(self.add_files)
        self.file_list.currentRowChanged.connect(
            self.preview_selected
        )
        layout.addWidget(self.file_list, 1)

        row = QHBoxLayout()

        add_button = QPushButton("Добавить")
        add_button.clicked.connect(self.choose_files)

        remove_button = QPushButton("Удалить")
        remove_button.clicked.connect(self.remove_selected)

        clear_button = QPushButton("Очистить")
        clear_button.clicked.connect(self.clear_files)

        row.addWidget(add_button)
        row.addWidget(remove_button)
        row.addWidget(clear_button)
        layout.addLayout(row)

        self.merge_checkbox = QCheckBox(
            "Объединить входные файлы перед обработкой"
        )
        self.merge_checkbox.setChecked(True)
        layout.addWidget(self.merge_checkbox)

        return box

    def _settings_panel(self) -> QWidget:
        container = QWidget()
        outer = QVBoxLayout(container)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        body = QWidget()
        layout = QVBoxLayout(body)
        scroll.setWidget(body)

        basic = QGroupBox("2. Базовая обработка")
        basic_layout = QVBoxLayout(basic)

        self.trim_checkbox = QCheckBox(
            "Убирать пробелы по краям текста"
        )
        self.trim_checkbox.setChecked(True)

        self.empty_checkbox = QCheckBox(
            "Удалять полностью пустые строки"
        )
        self.empty_checkbox.setChecked(True)

        self.source_checkbox = QCheckBox(
            "Добавить _source_file"
        )

        basic_layout.addWidget(self.trim_checkbox)
        basic_layout.addWidget(self.empty_checkbox)
        basic_layout.addWidget(self.source_checkbox)

        dedupe_form = QFormLayout()
        self.dedupe_checkbox = QCheckBox("Удалять дубли")
        self.dedupe_column = QComboBox()
        self.dedupe_column.addItem("Вся строка", None)
        dedupe_form.addRow(self.dedupe_checkbox)
        dedupe_form.addRow("По столбцу:", self.dedupe_column)
        basic_layout.addLayout(dedupe_form)

        sort_form = QFormLayout()
        self.sort_checkbox = QCheckBox("Сортировать")
        self.sort_column = QComboBox()

        self.sort_order = QComboBox()
        self.sort_order.addItem("По возрастанию", True)
        self.sort_order.addItem("По убыванию", False)

        sort_form.addRow(self.sort_checkbox)
        sort_form.addRow("Столбец:", self.sort_column)
        sort_form.addRow("Порядок:", self.sort_order)
        basic_layout.addLayout(sort_form)

        layout.addWidget(basic)

        filters = QGroupBox("3. Фильтры")
        filters_layout = QVBoxLayout(filters)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Правила:"))

        self.filter_mode = QComboBox()
        self.filter_mode.addItem(
            "Все одновременно (AND)",
            "all",
        )
        self.filter_mode.addItem(
            "Хотя бы одно (OR)",
            "any",
        )
        mode_row.addWidget(self.filter_mode, 1)
        filters_layout.addLayout(mode_row)

        self.filters_container = QWidget()
        self.filters_layout = QVBoxLayout(self.filters_container)
        self.filters_layout.setContentsMargins(0, 0, 0, 0)
        filters_layout.addWidget(self.filters_container)

        add_filter = QPushButton("+ Добавить фильтр")
        add_filter.clicked.connect(self.add_filter_row)
        filters_layout.addWidget(add_filter)

        layout.addWidget(filters)

        export = QGroupBox("4. Экспорт")
        export_layout = QFormLayout(export)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["XLSX", "CSV", "JSON"])

        self.output_mode = QComboBox()
        self.output_mode.addItem("Один результат", "single")
        self.output_mode.addItem(
            "Несколько файлов по значениям столбца",
            "split",
        )
        self.output_mode.currentIndexChanged.connect(
            self.sync_split_controls
        )

        self.split_column = QComboBox()
        self.split_column.currentTextChanged.connect(
            self.clear_split_values
        )

        self.load_values_button = QPushButton(
            "Загрузить значения для выбора"
        )
        self.load_values_button.clicked.connect(
            self.load_split_values
        )

        self.split_values = QListWidget()
        self.split_values.setSelectionMode(
            QAbstractItemView.ExtendedSelection
        )
        self.split_values.setMaximumHeight(140)

        self.output_dir = QLineEdit(
            str(Path.cwd() / "output")
        )
        choose_dir = QPushButton("Папка…")
        choose_dir.clicked.connect(self.choose_output_dir)

        dir_row = QHBoxLayout()
        dir_row.addWidget(self.output_dir, 1)
        dir_row.addWidget(choose_dir)

        self.base_name = QLineEdit("result")

        export_layout.addRow("Формат:", self.format_combo)
        export_layout.addRow("Режим:", self.output_mode)
        export_layout.addRow("Разделить по:", self.split_column)
        export_layout.addRow("", self.load_values_button)
        export_layout.addRow("Значения:", self.split_values)
        export_layout.addRow("Имя результата:", self.base_name)
        export_layout.addRow("Папка:", dir_row)

        layout.addWidget(export)
        layout.addStretch(1)

        self.sync_split_controls()

        return container

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #151922;
                color: #e8edf3;
                font-size: 13px;
            }
            QGroupBox {
                border: 1px solid #303744;
                border-radius: 10px;
                margin-top: 12px;
                padding: 11px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 5px;
            }
            QLabel#title {
                font-size: 27px;
                font-weight: 700;
            }
            QLabel#subtitle {
                color: #98a4b3;
            }
            QLabel#dropHint {
                color: #aab4c2;
                padding: 12px;
                border: 1px dashed #455065;
                border-radius: 8px;
            }
            QListWidget, QTableWidget, QTextEdit,
            QLineEdit, QComboBox, QScrollArea {
                background: #0f131a;
                border: 1px solid #303744;
                border-radius: 7px;
                padding: 5px;
            }
            QPushButton {
                background: #252c38;
                border: 1px solid #3a4352;
                border-radius: 7px;
                padding: 7px 11px;
            }
            QPushButton:hover {
                background: #303846;
            }
            QPushButton#primaryButton {
                background: #2b6de5;
                border: 1px solid #3c7bf0;
                font-weight: 700;
                padding: 9px 22px;
            }
            QProgressBar {
                border: 1px solid #303744;
                border-radius: 6px;
                text-align: center;
                background: #0f131a;
            }
            QProgressBar::chunk {
                background: #2b6de5;
                border-radius: 5px;
            }
            """
        )

    def choose_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите файлы",
            "",
            "Таблицы (*.xlsx *.csv *.json)",
        )
        if files:
            self.add_files(files)

    def add_files(self, paths: list[str]) -> None:
        for raw in paths:
            path = str(Path(raw).resolve())
            if path in self.file_paths:
                continue

            self.file_paths.append(path)
            item = QListWidgetItem(Path(path).name)
            item.setToolTip(path)
            self.file_list.addItem(item)

        self.refresh_columns()

        if self.file_list.count() and self.file_list.currentRow() < 0:
            self.file_list.setCurrentRow(0)

        self.log_message(
            f"Всего входных файлов: {len(self.file_paths)}"
        )

    def remove_selected(self) -> None:
        row = self.file_list.currentRow()
        if row < 0:
            return

        self.file_list.takeItem(row)
        del self.file_paths[row]
        self.refresh_columns()

        if self.file_paths:
            self.file_list.setCurrentRow(
                min(row, len(self.file_paths) - 1)
            )
        else:
            self.clear_preview()

    def clear_files(self) -> None:
        self.file_paths.clear()
        self.file_list.clear()
        self.columns = []
        self.refresh_columns()
        self.clear_preview()
        self.log_message("Список файлов очищен.")

    def refresh_columns(self) -> None:
        columns: list[str] = []

        for path in self.file_paths:
            try:
                for column in read_columns(path):
                    if column not in columns:
                        columns.append(column)
            except Exception as exc:
                self.log_message(
                    f"Не удалось прочитать столбцы {Path(path).name}: {exc}"
                )

        self.columns = columns

        current_dedupe = self.dedupe_column.currentText()
        self.dedupe_column.clear()
        self.dedupe_column.addItem("Вся строка", None)
        for column in columns:
            self.dedupe_column.addItem(column, column)
        if current_dedupe in columns:
            self.dedupe_column.setCurrentText(current_dedupe)

        self._reset_combo(self.sort_column, columns)
        self._reset_combo(self.split_column, columns)

        for row in self.filter_rows:
            row.set_columns(columns)

        self.clear_split_values()

    def _reset_combo(
        self,
        combo: QComboBox,
        values: list[str],
    ) -> None:
        current = combo.currentText()
        combo.clear()
        combo.addItems(values)
        if current in values:
            combo.setCurrentText(current)

    def add_filter_row(self) -> None:
        row = FilterRow(self.columns)
        row.remove_requested.connect(self.remove_filter_row)
        self.filter_rows.append(row)
        self.filters_layout.addWidget(row)

    def remove_filter_row(self, row: FilterRow) -> None:
        if len(self.filter_rows) == 1:
            row.enabled.setChecked(False)
            row.value.clear()
            return

        self.filter_rows.remove(row)
        row.setParent(None)
        row.deleteLater()

    def build_filters(self) -> list[FilterRule]:
        result: list[FilterRule] = []

        for row in self.filter_rows:
            column = row.column.currentText().strip()
            operator = row.operator.currentData()

            if not column:
                continue

            result.append(
                FilterRule(
                    column=column,
                    operator=operator,
                    value=row.value.text(),
                    enabled=row.enabled.isChecked(),
                )
            )

        return result

    def preview_selected(self, row: int) -> None:
        if row < 0 or row >= len(self.file_paths):
            self.clear_preview()
            return

        try:
            df = read_table(self.file_paths[row]).head(50)
            self.show_dataframe(df)
        except Exception as exc:
            self.log_message(f"Ошибка предпросмотра: {exc}")

    def show_dataframe(self, df: pd.DataFrame) -> None:
        preview = df.head(50)

        self.preview.clear()
        self.preview.setRowCount(len(preview))
        self.preview.setColumnCount(len(preview.columns))
        self.preview.setHorizontalHeaderLabels(
            [str(x) for x in preview.columns]
        )

        for r in range(len(preview)):
            for c, column in enumerate(preview.columns):
                value = preview.iloc[r, c]
                text = "" if pd.isna(value) else str(value)
                self.preview.setItem(
                    r,
                    c,
                    QTableWidgetItem(text),
                )

        self.preview.resizeColumnsToContents()

    def clear_preview(self) -> None:
        self.preview.clear()
        self.preview.setRowCount(0)
        self.preview.setColumnCount(0)

    def sync_split_controls(self) -> None:
        enabled = self.output_mode.currentData() == "split"
        self.split_column.setEnabled(enabled)
        self.load_values_button.setEnabled(enabled)
        self.split_values.setEnabled(enabled)

    def clear_split_values(self) -> None:
        self.split_values.clear()

    def load_split_values(self) -> None:
        if not self.file_paths:
            QMessageBox.warning(
                self,
                "Нет файлов",
                "Сначала добавьте входные файлы.",
            )
            return

        column = self.split_column.currentText()
        if not column:
            return

        try:
            values, truncated = collect_unique_values(
                self.file_paths,
                column,
                limit=1000,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка",
                str(exc),
            )
            return

        self.split_values.clear()
        for value in values:
            self.split_values.addItem(value)

        if truncated:
            self.log_message(
                "Уникальных значений больше 1000. "
                "Для списка показаны первые 1000."
            )
        else:
            self.log_message(
                f"Загружено уникальных значений: {len(values)}"
            )

    def choose_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Папка для результатов",
            self.output_dir.text(),
        )
        if path:
            self.output_dir.setText(path)

    def build_processing_options(self) -> ProcessingOptions:
        return ProcessingOptions(
            merge_files=self.merge_checkbox.isChecked(),
            trim_text=self.trim_checkbox.isChecked(),
            drop_empty_rows=self.empty_checkbox.isChecked(),
            drop_duplicates=self.dedupe_checkbox.isChecked(),
            duplicate_column=self.dedupe_column.currentData(),
            sort_rows=self.sort_checkbox.isChecked(),
            sort_column=self.sort_column.currentData(),
            sort_ascending=bool(self.sort_order.currentData()),
            add_source_column=self.source_checkbox.isChecked(),
            filters=self.build_filters(),
            filter_mode=self.filter_mode.currentData(),
        )

    def build_export_options(self) -> ExportOptions:
        selected_values = [
            item.text()
            for item in self.split_values.selectedItems()
        ]

        return ExportOptions(
            output_dir=self.output_dir.text().strip() or "output",
            base_name=self.base_name.text().strip() or "result",
            file_format=self.format_combo.currentText().lower(),
            mode=self.output_mode.currentData(),
            split_column=(
                self.split_column.currentText()
                if self.output_mode.currentData() == "split"
                else None
            ),
            split_values=selected_values,
        )

    def start_processing(self) -> None:
        if not self.file_paths:
            QMessageBox.warning(
                self,
                "Нет файлов",
                "Добавьте хотя бы один файл.",
            )
            return

        self.progress.setValue(0)
        self.run_button.setEnabled(False)

        self.worker_thread = QThread(self)
        self.worker = ProcessingWorker(
            self.file_paths.copy(),
            self.build_processing_options(),
            self.build_export_options(),
        )
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.failed.connect(self.on_failed)

        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(
            self.worker_thread.deleteLater
        )

        self.worker_thread.start()

    def on_progress(self, value: int, message: str) -> None:
        self.progress.setValue(value)
        self.log_message(message)

    def on_finished(self, tables, paths) -> None:
        self.run_button.setEnabled(True)

        if tables:
            self.show_dataframe(tables[0].dataframe)

        self.log_message(
            f"Готово. Создано файлов: {len(paths)}"
        )

        text = "\n".join(str(path) for path in paths[:10])
        if len(paths) > 10:
            text += f"\n… и ещё {len(paths) - 10}"

        box = QMessageBox(self)
        box.setWindowTitle("Готово")
        box.setText(
            f"Создано файлов: {len(paths)}\n\n{text}"
        )

        open_folder = box.addButton(
            "Открыть папку",
            QMessageBox.ActionRole,
        )
        box.addButton("Закрыть", QMessageBox.RejectRole)
        box.exec()

        if box.clickedButton() == open_folder and paths:
            open_in_file_manager(Path(paths[0]).parent)

        self.worker = None
        self.worker_thread = None

    def on_failed(self, error: str) -> None:
        self.run_button.setEnabled(True)
        self.log_message(f"Ошибка: {error}")
        QMessageBox.critical(self, "Ошибка", error)

        self.worker = None
        self.worker_thread = None

    def log_message(self, text: str) -> None:
        self.log.append(text)
