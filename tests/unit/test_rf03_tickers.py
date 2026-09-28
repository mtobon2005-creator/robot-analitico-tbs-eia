"""Pruebas RF-03: colección dinámica de tickers."""
import pytest

from src.tickers import (
    DuplicateTicker,
    InvalidTicker,
    TickerNotFound,
    add_ticker,
    add_tickers_bulk,
    is_ready_for_comparison,
    is_ready_for_single_asset,
    missing_for_comparison,
    normalize_ticker,
    parse_ticker_list,
    remove_ticker,
)


def test_normalize_strips_and_uppercases():
    assert normalize_ticker("  aapl  ") == "AAPL"


def test_add_ticker_returns_new_list_not_mutated():
    original = ["AAPL"]
    result = add_ticker(original, "msft")
    assert result == ["AAPL", "MSFT"]
    assert original == ["AAPL"]  # no se mutó la lista original


def test_add_ticker_rejects_empty():
    with pytest.raises(InvalidTicker):
        add_ticker([], "   ")


def test_add_ticker_rejects_invalid_characters():
    with pytest.raises(InvalidTicker):
        add_ticker([], "AAPL 123!")


def test_add_ticker_allows_dot_and_hyphen_suffixes():
    result = add_ticker([], "brk.b")
    assert result == ["BRK.B"]


def test_add_ticker_rejects_duplicate_case_insensitive():
    with pytest.raises(DuplicateTicker):
        add_ticker(["AAPL"], "aapl")


def test_add_ticker_rejects_too_long():
    with pytest.raises(InvalidTicker):
        add_ticker([], "A" * 21)


def test_remove_ticker_removes_existing():
    result = remove_ticker(["AAPL", "MSFT"], "aapl")
    assert result == ["MSFT"]


def test_remove_ticker_raises_if_missing():
    with pytest.raises(TickerNotFound):
        remove_ticker(["AAPL"], "MSFT")


def test_is_ready_for_single_asset():
    assert is_ready_for_single_asset(["AAPL"]) is True
    assert is_ready_for_single_asset([]) is False
    assert is_ready_for_single_asset(["AAPL", "MSFT"]) is False


def test_is_ready_for_comparison_requires_minimum_20():
    nineteen = [f"TICK{i}" for i in range(19)]
    twenty = [f"TICK{i}" for i in range(20)]
    assert is_ready_for_comparison(nineteen) is False
    assert is_ready_for_comparison(twenty) is True


def test_is_ready_for_comparison_allows_more_than_20():
    twenty_five = [f"TICK{i}" for i in range(25)]
    assert is_ready_for_comparison(twenty_five) is True


def test_is_ready_for_comparison_counts_unique_only():
    # 25 elementos pero solo 15 tickers únicos -> no alcanza el mínimo.
    repeated = [f"TICK{i % 15}" for i in range(25)]
    assert is_ready_for_comparison(repeated) is False


def test_missing_for_comparison_reports_gap():
    thirteen = [f"TICK{i}" for i in range(13)]
    assert missing_for_comparison(thirteen) == 7


def test_missing_for_comparison_zero_when_ready():
    twenty = [f"TICK{i}" for i in range(20)]
    assert missing_for_comparison(twenty) == 0


def test_add_ticker_allows_invalid_looking_test_ticker_for_fixture():
    # El fixture oficial usa EIA_INVALID_2026 como caso de fallo parcial
    # (T-06) — el FORMATO es válido, solo no existirá en el proveedor
    # real (eso se valida en RF-08, no aquí).
    result = add_ticker([], "EIA_INVALID_2026")
    assert result == ["EIA_INVALID_2026"]


def test_parse_ticker_list_splits_on_comma_space_and_newline():
    raw = "AAPL, MSFT\nBRK.B   GOOGL,,TSLA"
    assert parse_ticker_list(raw) == ["AAPL", "MSFT", "BRK.B", "GOOGL", "TSLA"]


def test_parse_ticker_list_empty_text_returns_empty_list():
    assert parse_ticker_list("   \n  ") == []


def test_add_tickers_bulk_adds_all_valid_new_tickers():
    collection, errors = add_tickers_bulk([], "aapl, msft brk.b")
    assert collection == ["AAPL", "MSFT", "BRK.B"]
    assert errors == []


def test_add_tickers_bulk_isolates_invalid_without_blocking_others():
    collection, errors = add_tickers_bulk([], "AAPL, BAD TICKER!, MSFT")
    # "TICKER!" es inválido por el símbolo; "BAD" sí es válido como ticker.
    assert "AAPL" in collection and "MSFT" in collection and "BAD" in collection
    assert len(errors) == 1
    assert errors[0][0] == "TICKER!"


def test_add_tickers_bulk_isolates_duplicate_with_existing_collection():
    collection, errors = add_tickers_bulk(["AAPL"], "aapl, msft")
    assert collection == ["AAPL", "MSFT"]
    assert len(errors) == 1
    assert errors[0][0] == "AAPL"


def test_add_tickers_bulk_isolates_duplicate_within_same_paste():
    collection, errors = add_tickers_bulk([], "AAPL AAPL MSFT")
    assert collection == ["AAPL", "MSFT"]
    assert len(errors) == 1
    assert errors[0][0] == "AAPL"


def test_add_tickers_bulk_does_not_mutate_original_collection():
    original = ["AAPL"]
    add_tickers_bulk(original, "MSFT")
    assert original == ["AAPL"]
