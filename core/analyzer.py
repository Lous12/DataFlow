from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from core.readers import read_table


@dataclass
class Suggestion:
    code: str
    title: str
    description: str
    action: str
    params: dict[str, Any] = field(default_factory=dict)
    priority: int = 50


@dataclass
class AnalysisReport:
    files_count: int
    total_rows: int
    columns: list[str]
    common_columns: list[str]
    differing_schemas: bool
    empty_rows: int
    full_duplicates: int
    whitespace_cells: int
    missing_by_column: dict[str, int]
    unique_by_column: dict[str, int]
    suggestions: list[Suggestion]


CITY_HINTS = {"city", "город", "town", "location", "region", "регион"}
CATEGORY_HINTS = {"category", "категория", "type", "тип", "group", "группа"}
ARTICLE_HINTS = {"article", "артикул", "sku", "id", "product_id", "item_id"}
PRICE_HINTS = {"price", "цена", "cost", "стоимость", "amount", "сумма"}
NAME_HINTS = {"name", "название", "title", "наименование", "product_name"}


def _normalize_name(name: str) -> str:
    return str(name).strip().casefold()


def _column_role(column: str) -> str | None:
    name = _normalize_name(column)
    if name in CITY_HINTS:
        return "city"
    if name in CATEGORY_HINTS:
        return "category"
    if name in ARTICLE_HINTS:
        return "article"
    if name in PRICE_HINTS:
        return "price"
    if name in NAME_HINTS:
        return "name"
    return None


def _count_whitespace_cells(df: pd.DataFrame) -> int:
    total = 0
    text_columns = df.select_dtypes(include=["object", "string"]).columns

    for column in text_columns:
        series = df[column].dropna()
        if series.empty:
            continue
        strings = series.astype(str)
        total += int((strings != strings.str.strip()).sum())

    return total


def analyze_files(file_paths: list[str]) -> AnalysisReport:
    if not file_paths:
        raise ValueError("Нет файлов для анализа.")

    loaded: list[tuple[Path, pd.DataFrame]] = []
    for raw_path in file_paths:
        path = Path(raw_path)
        loaded.append((path, read_table(path)))

    column_sets = [set(map(str, df.columns)) for _, df in loaded]
    all_columns: list[str] = []
    for _, df in loaded:
        for column in map(str, df.columns):
            if column not in all_columns:
                all_columns.append(column)

    common_columns = sorted(set.intersection(*column_sets)) if column_sets else []
    differing_schemas = any(s != column_sets[0] for s in column_sets[1:])

    combined = pd.concat(
        [df for _, df in loaded],
        ignore_index=True,
        sort=False,
    )

    total_rows = len(combined)
    empty_rows = int(combined.isna().all(axis=1).sum())
    full_duplicates = int(combined.duplicated().sum())
    whitespace_cells = _count_whitespace_cells(combined)

    missing_by_column = {
        str(column): int(combined[column].isna().sum())
        for column in combined.columns
    }
    unique_by_column = {
        str(column): int(combined[column].nunique(dropna=True))
        for column in combined.columns
    }

    suggestions: list[Suggestion] = []

    if len(file_paths) > 1:
        if differing_schemas:
            suggestions.append(
                Suggestion(
                    "schema_warning",
                    "Проверить структуру файлов",
                    "У файлов отличаются наборы столбцов. При объединении часть "
                    "ячеек станет пустой. Лучше проверить предпросмотр.",
                    "info",
                    priority=100,
                )
            )
        else:
            suggestions.append(
                Suggestion(
                    "merge_files",
                    "Объединить файлы",
                    f"У всех {len(file_paths)} файлов одинаковая структура. "
                    "Их можно безопасно объединить в одну таблицу.",
                    "merge_files",
                    priority=95,
                )
            )

    if empty_rows:
        suggestions.append(
            Suggestion(
                "drop_empty_rows",
                "Удалить пустые строки",
                f"Найдено полностью пустых строк: {empty_rows}.",
                "drop_empty_rows",
                priority=90,
            )
        )

    if whitespace_cells:
        suggestions.append(
            Suggestion(
                "trim_text",
                "Очистить пробелы в тексте",
                f"Найдено ячеек с лишними пробелами по краям: {whitespace_cells}.",
                "trim_text",
                priority=80,
            )
        )

    if full_duplicates:
        suggestions.append(
            Suggestion(
                "drop_full_duplicates",
                "Удалить полные дубли",
                f"Найдено полностью одинаковых строк: {full_duplicates}.",
                "drop_duplicates",
                priority=85,
            )
        )

    for column in all_columns:
        role = _column_role(column)
        unique_count = unique_by_column.get(column, 0)
        missing_count = missing_by_column.get(column, 0)

        if missing_count and total_rows:
            ratio = missing_count / total_rows
            if ratio >= 0.10:
                suggestions.append(
                    Suggestion(
                        f"missing:{column}",
                        f"Проверить пропуски: {column}",
                        f"В столбце «{column}» пусто {missing_count} из "
                        f"{total_rows} строк ({ratio:.0%}).",
                        "info",
                        {"column": column},
                        70,
                    )
                )

        if role == "article" and unique_count < total_rows:
            suggestions.append(
                Suggestion(
                    f"dedupe:{column}",
                    f"Убрать повторы по «{column}»",
                    f"Столбец похож на артикул/ID. Уникальных значений: "
                    f"{unique_count} из {total_rows}.",
                    "dedupe_column",
                    {"column": column},
                    98,
                )
            )

        if role in {"city", "category"} and 1 < unique_count <= 100:
            label = "городам" if role == "city" else "категориям"
            suggestions.append(
                Suggestion(
                    f"split:{column}",
                    f"Разделить результат по «{column}»",
                    f"Найдено уникальных значений: {unique_count}. "
                    f"Можно создать отдельные файлы по {label}.",
                    "split_column",
                    {"column": column},
                    88,
                )
            )

        if role == "price":
            numeric = pd.to_numeric(combined[column], errors="coerce").dropna()
            if not numeric.empty:
                median = float(numeric.median())
                suggestions.append(
                    Suggestion(
                        f"price:{column}",
                        f"Можно фильтровать по цене «{column}»",
                        f"Диапазон: {float(numeric.min()):g} — "
                        f"{float(numeric.max()):g}. Можно задать порог цены.",
                        "add_filter",
                        {
                            "column": column,
                            "operator": "gte",
                            "value": str(round(median, 2)),
                        },
                        55,
                    )
                )

        if role == "name":
            suggestions.append(
                Suggestion(
                    f"name:{column}",
                    f"Можно искать по названию «{column}»",
                    "Для текстового столбца удобно использовать фильтр "
                    "«Содержит».",
                    "add_filter",
                    {
                        "column": column,
                        "operator": "contains",
                        "value": "",
                    },
                    40,
                )
            )

    role_columns = {
        column for column in all_columns
        if _column_role(column) is not None
    }

    for column in all_columns:
        if column in role_columns:
            continue
        unique_count = unique_by_column.get(column, 0)
        if 2 <= unique_count <= 20 and total_rows >= unique_count * 2:
            suggestions.append(
                Suggestion(
                    f"generic_split:{column}",
                    f"Столбец «{column}» похож на категорию",
                    f"В нём {unique_count} уникальных значений. Его можно "
                    "использовать для фильтрации или разделения результата.",
                    "split_column",
                    {"column": column},
                    45,
                )
            )

    suggestions.sort(key=lambda item: item.priority, reverse=True)

    return AnalysisReport(
        files_count=len(file_paths),
        total_rows=total_rows,
        columns=all_columns,
        common_columns=common_columns,
        differing_schemas=differing_schemas,
        empty_rows=empty_rows,
        full_duplicates=full_duplicates,
        whitespace_cells=whitespace_cells,
        missing_by_column=missing_by_column,
        unique_by_column=unique_by_column,
        suggestions=suggestions,
    )
