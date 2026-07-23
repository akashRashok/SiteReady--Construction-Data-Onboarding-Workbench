"""Unit tests for deterministic normalisation helpers."""

from __future__ import annotations

from datetime import date

from app.pipeline.ids import certification_id, company_id, worker_id
from app.pipeline.normalise import (
    map_trade,
    normalise_phone,
    parse_date_value,
    validate_abn,
    validate_email,
)


def test_abn_valid():
    abn, err = validate_abn("51 824 753 556")
    assert err is None
    assert abn == "51824753556"


def test_abn_invalid_checksum():
    abn, err = validate_abn("12 345 678 901")
    assert abn is None
    assert err is not None


def test_abn_wrong_length():
    abn, err = validate_abn("12345")
    assert abn is None
    assert "11 digits" in (err or "")


def test_parse_iso_date():
    d, err = parse_date_value("2022-03-15")
    assert err is None
    assert d == date(2022, 3, 15)


def test_parse_au_slash_unambiguous():
    d, err = parse_date_value("15/03/2022")
    assert err is None
    assert d == date(2022, 3, 15)


def test_parse_dd_mmm_yy():
    d, err = parse_date_value("10-Jan-23")
    assert err is None
    assert d == date(2023, 1, 10)


def test_ambiguous_date():
    d, err = parse_date_value("05/06/2023")
    assert d is None
    assert err and "Ambiguous" in err


def test_unparseable_date():
    d, err = parse_date_value("99/99/2020")
    assert d is None
    assert err and "Unparseable" in err


def test_email_invalid():
    email, err = validate_email("not-an-email")
    assert email is None
    assert err


def test_email_valid():
    email, err = validate_email("Sarah.Chen@Example.COM")
    assert email == "sarah.chen@example.com"
    assert err is None


def test_phone_au_mobile():
    phone, err = normalise_phone("0412 345 678")
    assert err is None
    assert phone == "+61412345678"


def test_phone_invalid():
    phone, err = normalise_phone("0411555ABCD")
    assert phone is None
    assert err


def test_trade_alias():
    trade, known = map_trade("Sparky")
    assert known
    assert trade.value == "electrician"


def test_stable_ids_deterministic():
    a1, _ = company_id("apex build", "51824753556")
    a2, _ = company_id("apex build", "51824753556")
    assert a1 == a2
    w1, _ = worker_id("Sarah Chen", a1, "sarah.chen@apexbuild.example")
    w2, _ = worker_id("Sarah Chen", a1, "sarah.chen@apexbuild.example")
    assert w1 == w2
    c1, _ = certification_id(w1, "white_card", "WC-10001")
    c2, _ = certification_id(w1, "white_card", "WC-10001")
    assert c1 == c2
