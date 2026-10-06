from pathlib import Path
import re
import pandas as pd

from core.models import ExportOptions, ProcessedTable


def _safe_filename(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*]+', "_", str(value).strip())
    value = re.sub(r"\s+", " ", value).strip(" .")
    return value[:100] or "empty"


def _save(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ext = path.suffix.lower()

    if ext == ".xlsx":
        df.to_excel(path, index=False)
    elif ext == ".csv":
        df.to_csv(path, index=False, encoding="utf-8-sig")
    elif ext == ".json":
        df.to_json(
            path,
            orient="records",
            force_ascii=False,
            indent=2,
        )
    else:
        raise ValueError(f"Неподдерживаемый формат: {ext}")


def export_processed_tables(
    tables: list[ProcessedTable],
    options: ExportOptions,
) -> list[Path]:
    output_dir = Path(options.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ext = "." + options.file_format.lower().lstrip(".")
    written: list[Path] = []

    for table in tables:
        df = table.dataframe
        table_prefix = ""
        if len(tables) > 1:
            table_prefix = _safe_filename(table.name) + "_"

        if options.mode == "split":
            column = options.split_column
            if not column:
                raise ValueError(
                    "Для нескольких файлов выберите столбец разделения."
                )
            if column not in df.columns:
                raise ValueError(
                    f"Столбец разделения не найден: {column}"
                )

            wanted = {str(x).strip() for x in options.split_values if str(x).strip()}

            grouped = df.groupby(column, dropna=False, sort=True)

            for raw_value, subset in grouped:
                display = "EMPTY" if pd.isna(raw_value) else str(raw_value).strip()

                if wanted and display not in wanted:
                    continue

                filename = (
                    f"{table_prefix}{_safe_filename(options.base_name)}_"
                    f"{_safe_filename(column)}_"
                    f"{_safe_filename(display)}{ext}"
                )
                path = output_dir / filename
                _save(subset.reset_index(drop=True), path)
                written.append(path)
        else:
            filename = (
                f"{table_prefix}{_safe_filename(options.base_name)}{ext}"
            )
            path = output_dir / filename
            _save(df, path)
            written.append(path)

    if not written:
        raise ValueError("После выбранных условий не создано ни одного файла.")

    return written
