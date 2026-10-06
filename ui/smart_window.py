from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from core.analyzer import AnalysisReport, Suggestion, analyze_files
from ui.main_window import MainWindow


class SmartMainWindow(MainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("DataFlow v0.2 — умный анализ файлов")
        self.analysis_report: AnalysisReport | None = None

        self._build_analysis_panel()

    def _build_analysis_panel(self) -> None:
        group = QGroupBox("Умный анализ файлов")
        layout = QVBoxLayout(group)

        top = QHBoxLayout()

        self.analyze_button = QPushButton("Сканировать и предложить")
        self.analyze_button.clicked.connect(self.run_analysis)

        self.analysis_summary = QLabel(
            "Добавьте файлы и нажмите «Сканировать и предложить»."
        )
        self.analysis_summary.setWordWrap(True)

        top.addWidget(self.analyze_button)
        top.addWidget(self.analysis_summary, 1)
        layout.addLayout(top)

        self.suggestions_list = QListWidget()
        self.suggestions_list.setMaximumHeight(180)
        self.suggestions_list.setSelectionMode(
            QAbstractItemView.SingleSelection
        )
        layout.addWidget(self.suggestions_list)

        buttons = QHBoxLayout()

        apply_one = QPushButton("Применить выбранную подсказку")
        apply_one.clicked.connect(self.apply_selected_suggestion)

        apply_safe = QPushButton("Применить безопасные подсказки")
        apply_safe.clicked.connect(self.apply_safe_suggestions)

        buttons.addWidget(apply_one)
        buttons.addWidget(apply_safe)
        layout.addLayout(buttons)

        root = self.centralWidget().layout()
        root.insertWidget(2, group)

    def add_files(self, paths: list[str]) -> None:
        super().add_files(paths)
        self.invalidate_analysis()

    def remove_selected(self) -> None:
        super().remove_selected()
        self.invalidate_analysis()

    def clear_files(self) -> None:
        super().clear_files()
        self.invalidate_analysis()

    def invalidate_analysis(self) -> None:
        self.analysis_report = None

        if hasattr(self, "suggestions_list"):
            self.suggestions_list.clear()

        if hasattr(self, "analysis_summary"):
            self.analysis_summary.setText(
                "Файлы изменились. Запустите анализ заново."
            )

    def run_analysis(self) -> None:
        if not self.file_paths:
            QMessageBox.warning(
                self,
                "Нет файлов",
                "Сначала добавьте хотя бы один XLSX, CSV или JSON файл.",
            )
            return

        self.analyze_button.setEnabled(False)
        self.analysis_summary.setText("Сканирую файлы…")
        self.suggestions_list.clear()

        try:
            QApplication.processEvents()
            report = analyze_files(self.file_paths)
            self.analysis_report = report

            schema_text = (
                "структура файлов отличается"
                if report.differing_schemas
                else "структура совместима"
            )

            self.analysis_summary.setText(
                f"Файлов: {report.files_count} • "
                f"строк: {report.total_rows:,} • "
                f"столбцов: {len(report.columns)} • "
                f"{schema_text}. "
                f"Подсказок: {len(report.suggestions)}."
            )

            for suggestion in report.suggestions:
                item = QListWidgetItem(
                    f"{suggestion.title}\n{suggestion.description}"
                )
                item.setData(Qt.UserRole, suggestion.code)
                item.setToolTip(suggestion.description)
                self.suggestions_list.addItem(item)

            if not report.suggestions:
                self.suggestions_list.addItem(
                    "Явных проблем не найдено. "
                    "Можно настроить обработку вручную."
                )

            self.log_message(
                f"Анализ завершён: {report.total_rows:,} строк, "
                f"{len(report.suggestions)} подсказок."
            )
        except Exception as exc:
            self.analysis_summary.setText("Не удалось завершить анализ.")
            QMessageBox.critical(self, "Ошибка анализа", str(exc))
        finally:
            self.analyze_button.setEnabled(True)

    def _find_suggestion(self, code: str) -> Suggestion | None:
        if not self.analysis_report:
            return None

        for suggestion in self.analysis_report.suggestions:
            if suggestion.code == code:
                return suggestion

        return None

    def apply_selected_suggestion(self) -> None:
        item = self.suggestions_list.currentItem()

        if item is None:
            QMessageBox.information(
                self,
                "Подсказка не выбрана",
                "Выберите подсказку в списке.",
            )
            return

        code = item.data(Qt.UserRole)
        suggestion = self._find_suggestion(code)

        if suggestion is not None:
            self.apply_suggestion(suggestion)

    def apply_safe_suggestions(self) -> None:
        if not self.analysis_report:
            QMessageBox.information(
                self,
                "Нет анализа",
                "Сначала нажмите «Сканировать и предложить».",
            )
            return

        safe_actions = {
            "merge_files",
            "drop_empty_rows",
            "trim_text",
            "dedupe_column",
        }

        applied = 0

        for suggestion in self.analysis_report.suggestions:
            if suggestion.action in safe_actions:
                self.apply_suggestion(
                    suggestion,
                    show_message=False,
                )
                applied += 1

        QMessageBox.information(
            self,
            "Готово",
            f"Применено безопасных подсказок: {applied}.\n"
            "Фильтры и разделение файлов оставлены на ваш выбор.",
        )

    def apply_suggestion(
        self,
        suggestion: Suggestion,
        show_message: bool = True,
    ) -> None:
        action = suggestion.action
        params = suggestion.params

        if action == "merge_files":
            self.merge_checkbox.setChecked(True)

        elif action == "drop_empty_rows":
            self.empty_checkbox.setChecked(True)

        elif action == "trim_text":
            self.trim_checkbox.setChecked(True)

        elif action == "drop_duplicates":
            self.dedupe_checkbox.setChecked(True)
            self.dedupe_column.setCurrentIndex(0)

        elif action == "dedupe_column":
            column = params.get("column", "")
            self.dedupe_checkbox.setChecked(True)

            if column:
                self.dedupe_column.setCurrentText(column)

        elif action == "split_column":
            column = params.get("column", "")
            index = self.output_mode.findData("split")

            if index >= 0:
                self.output_mode.setCurrentIndex(index)

            if column:
                self.split_column.setCurrentText(column)

            self.sync_split_controls()

        elif action == "add_filter":
            self.add_filter_row()
            row = self.filter_rows[-1]

            column = params.get("column", "")
            operator = params.get("operator", "equals")
            value = params.get("value", "")

            if column:
                row.column.setCurrentText(column)

            index = row.operator.findData(operator)
            if index >= 0:
                row.operator.setCurrentIndex(index)

            row.value.setText(str(value))

        elif action == "info":
            if show_message:
                QMessageBox.information(
                    self,
                    suggestion.title,
                    suggestion.description,
                )
            return

        if show_message:
            QMessageBox.information(
                self,
                "Подсказка применена",
                suggestion.title,
            )
