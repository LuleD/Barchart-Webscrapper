"""Offline test for the table parser, using real values transcribed from a
screenshot of the target page (GCV26 volatility-greeks, side-by-side view).
No network/browser needed.
"""

from barchart_scraper.scraper import parse_table

HEADERS = [
    "Links", "Latest", "IV", "Delta", "Gamma", "Theta", "Vega", "IV Skew", "Type", "Last Trade",
    "Strike",
    "Latest", "IV", "Delta", "Gamma", "Theta", "Vega", "IV Skew", "Type", "Last Trade", "Links",
]

ROWS = [
    [
        "", "93.30s", "75.68%", "0.6174", "0.0023", "-32.4781", "0.8540", "+51.83%", "Call", "09/14/26",
        "4,230.00",
        "9.20s", "29.59%", "-0.2354", "0.0046", "-10.0240", "0.6885", "+5.74%", "Put", "09/14/26", "",
    ],
    [
        "", "31.90s", "37.36%", "0.4895", "0.0048", "-16.9270", "0.8927", "+13.52%", "Call", "09/14/26",
        "4,280.00",
        "29.00s", "30.76%", "-0.5141", "0.0058", "-13.4823", "0.8924", "+6.91%", "Put", "09/14/26", "",
    ],
    [
        "", "8.50", "0.00%", "0.1835", "0.0051", "-7.4302", "0.5946", "-23.85%", "Call", "03:50 CT",
        "4,325.00",
        "31.70s", "0.00%", "-0.8164", "0.0051", "-6.6456", "0.5946", "-23.85%", "Put", "09/14/26", "",
    ],
]


def test_parse_table_splits_calls_and_puts():
    result = parse_table(HEADERS, ROWS)
    assert len(result) == 6  # 3 rows x (1 call + 1 put)

    calls = [r for r in result if r.option_type == "call"]
    puts = [r for r in result if r.option_type == "put"]
    assert len(calls) == 3
    assert len(puts) == 3

    first_call = calls[0]
    assert first_call.strike == 4230.00
    assert first_call.latest == 93.30
    assert first_call.iv == 75.68
    assert first_call.delta == 0.6174
    assert first_call.gamma == 0.0023
    assert first_call.theta == -32.4781
    assert first_call.vega == 0.8540
    assert first_call.iv_skew == 51.83
    assert first_call.quote_type == "Call"
    assert first_call.last_trade == "09/14/26"

    first_put = puts[0]
    assert first_put.strike == 4230.00
    assert first_put.latest == 9.20
    assert first_put.delta == -0.2354

    # non-date "last trade" values (intraday times) pass through untouched
    last_call = calls[-1]
    assert last_call.last_trade == "03:50 CT"


def test_parse_table_requires_strike_column():
    import pytest

    with pytest.raises(ValueError):
        parse_table(["Latest", "IV"], [["1", "2"]])
