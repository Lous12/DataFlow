from dataclasses import dataclass, field
import pandas as pd


@dataclass
class FilterRule:
    column: str
    operator: str
    value: str = ""
    enabled: bool = True


@dataclass
class ProcessingOptions:
    merge_files: bool = True
    trim_text: bool = True
    drop_empty_rows: bool = True
    drop_duplicates: bool = False
    duplicate_column: str | None = None
    sort_rows: bool = False
    sort_column: str | None = None
    sort_ascending: bool = True
    add_source_column: bool = False
    filters: list[FilterRule] = field(default_factory=list)
    filter_mode: str = "all"  # all / any


@dataclass
class ProcessedTable:
    name: str
    dataframe: pd.DataFrame


@dataclass
class ExportOptions:
    output_dir: str = "output"
    base_name: str = "result"
    file_format: str = "xlsx"
    mode: str = "single"  # single / split
    split_column: str | None = None
    split_values: list[str] = field(default_factory=list)
