# DataFlow

A small desktop utility for processing, filtering and splitting Excel, CSV and JSON files.

DataFlow is built with **Python, PySide6 and pandas**. The project is aimed at repetitive data-cleaning tasks that are annoying to do manually: merging files, filtering rows, removing duplicates, sorting data and exporting multiple result files in one run.

> Current status: **v0.1.0 — early public version**

## Features

- Import multiple `.xlsx`, `.csv` and `.json` files
- Drag & drop support
- Preview table data
- Merge several files into one dataset
- Remove empty rows
- Trim whitespace in text cells
- Remove duplicates by full row or selected column
- Sort by a selected column
- Add the source filename as `_source_file`
- Add multiple filters at once
- Combine filters using **AND / OR**
- Filter by any detected column
- Supported filter operators:
  - equals / not equals
  - contains / does not contain
  - starts with / ends with
  - `>`, `>=`, `<`, `<=`
  - one of several values
  - empty / not empty
- Export to `.xlsx`, `.csv` or `.json`
- Split one processed dataset into multiple output files by a selected column
- Select only specific split values
- CLI mode using a JSON config
- Build a single Windows `.exe` with PyInstaller

## Example

A dataset contains:

```text
article | name      | category      | price | city
1001    | Notebook  | Stationery    | 250   | Moscow
1002    | Book      | Books         | 700   | Yakutsk
1003    | Keyboard  | Electronics   | 3500  | Kazan
```

You can create rules such as:

```text
city = Yakutsk
price >= 500
category is one of Books;Stationery
```

Then export the result as one file, or split it automatically:

```text
result_city_Yakutsk.xlsx
result_city_Moscow.xlsx
result_city_Kazan.xlsx
```

## Screenshots

A real application screenshot will be added here in a future update.

## Installation

Python 3.11+ is recommended.

```bash
git clone https://github.com/Lous12/DataFlow.git
cd DataFlow

python -m venv .venv
```

Windows:

```bat
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## CLI

The same processing core can be used without the GUI:

```bash
python cli.py --config config.example.json
```

Example config:

```json
{
  "input_files": [
    "input/products_1.csv",
    "input/products_2.csv"
  ],
  "merge_files": true,
  "drop_duplicates": true,
  "duplicate_column": "article",
  "filter_mode": "all",
  "filters": [
    {
      "column": "city",
      "operator": "equals",
      "value": "Yakutsk",
      "enabled": true
    },
    {
      "column": "price",
      "operator": "gte",
      "value": "500",
      "enabled": true
    }
  ],
  "output_dir": "output",
  "base_name": "result",
  "file_format": "xlsx",
  "output_mode": "single"
}
```

## Build Windows EXE

Run:

```bat
build_exe.bat
```

The script creates a virtual environment if needed, installs development dependencies and builds a one-file executable:

```text
dist\DataFlow.exe
```

## Project structure

```text
DataFlow/
├─ core/
│  ├─ exporters.py
│  ├─ models.py
│  ├─ processing.py
│  └─ readers.py
├─ ui/
│  ├─ main_window.py
│  └─ widgets.py
├─ tests/
│  └─ test_processing.py
├─ main.py
├─ cli.py
├─ config.example.json
├─ requirements.txt
├─ requirements-dev.txt
├─ build_exe.bat
├─ CHANGELOG.md
├─ LICENSE
└─ README.md
```

The processing logic is kept separate from the GUI so it can later be reused in a CLI tool, another desktop interface or an automation workflow.

## Development

Install development dependencies:

```bash
pip install -r requirements-dev.txt
```

Run tests:

```bash
pytest
```

## Roadmap

Planned improvements include:

- saved processing presets
- renaming and selecting columns from the GUI
- nested filter groups such as `(A AND B) OR (C AND D)`
- multiple independent export profiles in one run
- calculated columns
- better handling of very large datasets
- more Excel-specific tools

## License

MIT License.
