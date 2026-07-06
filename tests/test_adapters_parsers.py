import pytest

from app.adapters.parsers import ParserError, require_fields, require_mapping


def test_require_mapping_accepts_dict_payload():
    payload = {"symbol": "TEST"}

    assert require_mapping(payload) == payload


def test_require_mapping_rejects_non_dict_payload():
    with pytest.raises(ParserError):
        require_mapping(["TEST"])


def test_require_fields_accepts_present_fields():
    require_fields({"symbol": "TEST", "price": "1.23"}, ("symbol", "price"))


def test_require_fields_rejects_missing_fields():
    with pytest.raises(ParserError):
        require_fields({"symbol": "TEST"}, ("symbol", "price"))
