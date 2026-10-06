import pandas as pd

from core.analyzer import _column_role, _count_whitespace_cells


def test_column_roles():
    assert _column_role("city") == "city"
    assert _column_role("Категория") == "category"
    assert _column_role("SKU") == "article"
    assert _column_role("Цена") == "price"
    assert _column_role("Название") == "name"


def test_whitespace_detection():
    df = pd.DataFrame(
        {
            "name": ["Normal", " Left", "Right ", " Both "],
            "price": [1, 2, 3, 4],
        }
    )
    assert _count_whitespace_cells(df) == 3
