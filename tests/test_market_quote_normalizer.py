from app.services.market_quote_normalizer import normalize_market_quote


def test_normalizes_akshare_price_fields_to_market_quote_contract():
    quote = normalize_market_quote({"price": 5.51, "change_percent": 2.799})

    assert quote["close"] == 5.51
    assert quote["pct_chg"] == 2.799


def test_keeps_existing_standard_market_quote_fields():
    quote = normalize_market_quote(
        {"price": 5.51, "change_percent": 2.799, "close": 5.5, "pct_chg": 2.6}
    )

    assert quote["close"] == 5.5
    assert quote["pct_chg"] == 2.6
