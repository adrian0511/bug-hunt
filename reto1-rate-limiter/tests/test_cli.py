"""Tests del filtro completo stdin → stdout (Reto 1)."""

from __future__ import annotations

import io

import pytest

from rate_limiter.cli import process, run


def _run_filter(text: str) -> str:
    stdin = io.StringIO(text)
    stdout = io.StringIO()
    run(stdin, stdout)
    return stdout.getvalue()


def test_example_case_exact_stdout():
    """End-to-end: el ejemplo exacto debe producir la salida exacta esperada."""
    input_text = "2 1\n0 a\n0 a\n0 a\n500 a\n1000 a\n"
    expected = "ALLOW\nALLOW\nDENY\nDENY\nALLOW\n"
    assert _run_filter(input_text) == expected


def test_empty_input_produces_no_output():
    assert _run_filter("") == ""


def test_whitespace_only_input_produces_no_output():
    assert _run_filter("\n\n   \n\n") == ""


def test_blank_lines_are_ignored():
    """Las líneas en blanco intercaladas con peticiones no deben afectar el resultado."""
    input_text = "2 1\n\n0 a\n0 a\n\n0 a\n"
    expected = "ALLOW\nALLOW\nDENY\n"
    assert _run_filter(input_text) == expected


def test_config_only_no_requests():
    assert _run_filter("5 2\n") == ""


def test_multiple_keys_interleaved():
    """Dos keys intercaladas mantienen cubos independientes."""
    input_text = "1 0\n0 a\n0 b\n0 a\n0 b\n"
    expected = "ALLOW\nALLOW\nDENY\nDENY\n"
    assert _run_filter(input_text) == expected


def test_process_is_a_lazy_generator():
    """`process` genera los veredictos como un iterador, uno por petición."""
    results = list(process(["2 1", "0 a", "0 a", "0 a"]))
    assert results == ["ALLOW", "ALLOW", "DENY"]


def test_key_with_spaces_is_preserved():
    """La key es todo lo que va tras el timestamp (puede contener espacios)."""
    input_text = "1 0\n0 my key\n0 my key\n"
    expected = "ALLOW\nDENY\n"
    assert _run_filter(input_text) == expected


def test_trailing_carriage_returns_are_stripped():
    """Los finales de línea CRLF no deben romper el parseo."""
    input_text = "2 1\r\n0 a\r\n0 a\r\n"
    expected = "ALLOW\nALLOW\n"
    assert _run_filter(input_text) == expected


@pytest.mark.parametrize("bad_config", ["oops", "2", "2 1 3"])
def test_invalid_config_line_raises(bad_config):
    with pytest.raises(ValueError):
        list(process([bad_config, "0 a"]))


def test_invalid_request_line_raises():
    with pytest.raises(ValueError):
        list(process(["2 1", "not-a-timestamp"]))
