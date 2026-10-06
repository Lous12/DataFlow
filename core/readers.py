from pathlib import Path
import pandas as pd

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".json"}


def is_supported_file(path: str | Path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def read_table(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    ext = path.suffix.lower()

    if ext == ".csv":
        return pd.read_csv(path)
    if ext == ".xlsx":
        return pd.read_excel(path)
    if ext == ".json":
        return pd.read_json(path)

    raise ValueError(f"Неподдерживаемый формат: {ext}")


def read_columns(path: str | Path) -> list[str]:
    path = Path(path)
    ext = path.suffix.lower()

    if ext == ".csv":
        return [str(x) for x in pd.read_csv(path, nrows=0).columns]
    if ext == ".xlsx":
        return [str(x) for x in pd.read_excel(path, nrows=0).columns]
    if ext == ".json":
        return [str(x) for x in pd.read_json(path).columns]

    raise ValueError(f"Неподдерживаемый формат: {ext}")
