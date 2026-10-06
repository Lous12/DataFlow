import pandas as pd

from core.models import FilterRule, ProcessingOptions
from core.processing import apply_filters, clean_dataframe


def sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"article": 1001, "name": " Notebook ", "category": "Stationery", "price": 250, "city": "Moscow"},
            {"article": 1002, "name": "Book", "category": "Books", "price": 700, "city": "Yakutsk"},
            {"article": 1002, "name": "Book", "category": "Books", "price": 700, "city": "Yakutsk"},
            {"article": 1003, "name": "Keyboard", "category": "Electronics", "price": 3500, "city": "Kazan"},
        ]
    )


def test_multiple_filters_all_mode():
    df = sample_df()
    rules = [
        FilterRule("city", "equals", "Yakutsk"),
        FilterRule("price", "gte", "500"),
    ]

    result = apply_filters(df, rules, mode="all")

    assert len(result) == 2
    assert set(result["city"]) == {"Yakutsk"}


def test_multiple_filters_any_mode():
    df = sample_df()
    rules = [
        FilterRule("city", "equals", "Moscow"),
        FilterRule("category", "equals", "Electronics"),
    ]

    result = apply_filters(df, rules, mode="any")

    assert set(result["article"]) == {1001, 1003}


def test_cleaning_and_deduplication():
    df = sample_df()
    options = ProcessingOptions(
        trim_text=True,
        drop_empty_rows=True,
        drop_duplicates=True,
        duplicate_column="article",
    )

    result = clean_dataframe(df, options)

    assert len(result) == 3
    assert result.loc[result["article"] == 1001, "name"].iloc[0] == "Notebook"
