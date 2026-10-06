from pathlib import Path
import operator as py_operator
import pandas as pd

from core.models import FilterRule, ProcessedTable, ProcessingOptions
from core.readers import read_table


TEXT_OPERATORS = {
    "equals",
    "not_equals",
    "contains",
    "not_contains",
    "starts_with",
    "ends_with",
    "one_of",
}

NUMERIC_OPERATORS = {
    "gt",
    "gte",
    "lt",
    "lte",
}


def _string_series(series: pd.Series) -> pd.Series:
    return series.astype("string").fillna("").str.strip()


def _numeric_compare(series: pd.Series, value: str, op: str) -> pd.Series:
    try:
        target = float(str(value).replace(",", "."))
    except ValueError as exc:
        raise ValueError(f"Для числового фильтра нужно число: {value}") from exc

    numeric = pd.to_numeric(series, errors="coerce")

    funcs = {
        "gt": py_operator.gt,
        "gte": py_operator.ge,
        "lt": py_operator.lt,
        "lte": py_operator.le,
    }
    return funcs[op](numeric, target).fillna(False)


def build_filter_mask(df: pd.DataFrame, rule: FilterRule) -> pd.Series:
    if rule.column not in df.columns:
        raise ValueError(f"Столбец фильтра не найден: {rule.column}")

    series = df[rule.column]
    op = rule.operator
    value = rule.value

    if op == "empty":
        return (series.isna() | _string_series(series).eq("")).fillna(False)

    if op == "not_empty":
        return (~(series.isna() | _string_series(series).eq(""))).fillna(False)

    if op in NUMERIC_OPERATORS:
        return _numeric_compare(series, value, op)

    text = _string_series(series)
    target = str(value).strip()

    if op == "equals":
        if pd.api.types.is_numeric_dtype(series):
            try:
                return _numeric_compare(series, target, "gte") & _numeric_compare(series, target, "lte")
            except ValueError:
                pass
        return text.str.casefold().eq(target.casefold())

    if op == "not_equals":
        return ~text.str.casefold().eq(target.casefold())

    if op == "contains":
        return text.str.contains(target, case=False, regex=False, na=False)

    if op == "not_contains":
        return ~text.str.contains(target, case=False, regex=False, na=False)

    if op == "starts_with":
        return text.str.casefold().str.startswith(target.casefold(), na=False)

    if op == "ends_with":
        return text.str.casefold().str.endswith(target.casefold(), na=False)

    if op == "one_of":
        values = [x.strip().casefold() for x in target.split(";") if x.strip()]
        return text.str.casefold().isin(values)

    raise ValueError(f"Неизвестный оператор фильтра: {op}")


def apply_filters(
    df: pd.DataFrame,
    rules: list[FilterRule],
    mode: str = "all",
) -> pd.DataFrame:
    active = [rule for rule in rules if rule.enabled]
    if not active:
        return df

    masks = [build_filter_mask(df, rule) for rule in active]

    if mode == "any":
        final_mask = masks[0]
        for mask in masks[1:]:
            final_mask = final_mask | mask
    else:
        final_mask = masks[0]
        for mask in masks[1:]:
            final_mask = final_mask & mask

    return df.loc[final_mask].copy()


def clean_dataframe(
    df: pd.DataFrame,
    options: ProcessingOptions,
) -> pd.DataFrame:
    result = df.copy()

    if options.trim_text:
        columns = result.select_dtypes(include=["object", "string"]).columns
        for column in columns:
            result[column] = result[column].apply(
                lambda v: v.strip() if isinstance(v, str) else v
            )

    if options.drop_empty_rows:
        result = result.dropna(how="all")

    result = apply_filters(result, options.filters, options.filter_mode)

    if options.drop_duplicates:
        if options.duplicate_column:
            if options.duplicate_column not in result.columns:
                raise ValueError(
                    f"Столбец для удаления дублей не найден: "
                    f"{options.duplicate_column}"
                )
            result = result.drop_duplicates(
                subset=[options.duplicate_column]
            )
        else:
            result = result.drop_duplicates()

    if options.sort_rows and options.sort_column:
        if options.sort_column not in result.columns:
            raise ValueError(
                f"Столбец сортировки не найден: {options.sort_column}"
            )
        result = result.sort_values(
            options.sort_column,
            ascending=options.sort_ascending,
        )

    return result.reset_index(drop=True)


def process_file_set(
    file_paths: list[str],
    options: ProcessingOptions,
) -> list[ProcessedTable]:
    if not file_paths:
        raise ValueError("Не выбраны входные файлы.")

    loaded: list[tuple[str, pd.DataFrame]] = []

    for raw_path in file_paths:
        path = Path(raw_path)
        df = read_table(path)

        if options.add_source_column:
            df["_source_file"] = path.name

        loaded.append((path.stem, df))

    if options.merge_files:
        merged = pd.concat(
            [df for _, df in loaded],
            ignore_index=True,
            sort=False,
        )
        return [
            ProcessedTable(
                name="merged",
                dataframe=clean_dataframe(merged, options),
            )
        ]

    return [
        ProcessedTable(
            name=name,
            dataframe=clean_dataframe(df, options),
        )
        for name, df in loaded
    ]


def collect_unique_values(
    file_paths: list[str],
    column: str,
    limit: int = 1000,
) -> tuple[list[str], bool]:
    values: set[str] = set()

    for raw_path in file_paths:
        df = read_table(raw_path)
        if column not in df.columns:
            continue

        for value in df[column].dropna().unique():
            text = str(value).strip()
            if text:
                values.add(text)
            if len(values) > limit:
                return sorted(values)[:limit], True

    return sorted(values), False
