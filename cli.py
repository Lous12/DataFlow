import argparse
import json
from pathlib import Path

from core.models import ExportOptions, FilterRule, ProcessingOptions
from core.processing import process_file_set
from core.exporters import export_processed_tables


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DataFlow CLI")
    parser.add_argument("--config", default="config.example.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = Path(args.config)

    with config_path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    filters = [
        FilterRule(
            column=item["column"],
            operator=item["operator"],
            value=str(item.get("value", "")),
            enabled=item.get("enabled", True),
        )
        for item in cfg.get("filters", [])
    ]

    processing = ProcessingOptions(
        merge_files=cfg.get("merge_files", True),
        trim_text=cfg.get("trim_text", True),
        drop_empty_rows=cfg.get("drop_empty_rows", True),
        drop_duplicates=cfg.get("drop_duplicates", False),
        duplicate_column=cfg.get("duplicate_column"),
        sort_rows=cfg.get("sort_rows", False),
        sort_column=cfg.get("sort_column"),
        sort_ascending=cfg.get("sort_ascending", True),
        add_source_column=cfg.get("add_source_column", False),
        filters=filters,
        filter_mode=cfg.get("filter_mode", "all"),
    )

    export = ExportOptions(
        output_dir=cfg.get("output_dir", "output"),
        base_name=cfg.get("base_name", "result"),
        file_format=cfg.get("file_format", "xlsx"),
        mode=cfg.get("output_mode", "single"),
        split_column=cfg.get("split_column"),
        split_values=[str(x) for x in cfg.get("split_values", [])],
    )

    tables = process_file_set(cfg["input_files"], processing)
    paths = export_processed_tables(tables, export)

    print("Готово:")
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
