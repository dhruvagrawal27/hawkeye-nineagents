"""Feature-label translations."""

from app.services.feature_labels import format_value, label_for, normal_band


def test_known_labels():
    assert label_for("pass_rate") == "Balance pass-through rate"
    assert label_for("ps49").startswith("Structuring")
    assert label_for("g_ncp") == "Graph counterparty count"


def test_unknown_label_falls_back_to_name():
    assert label_for("nonexistent_feature_xyz") == "nonexistent_feature_xyz"


def test_pct_formatter():
    assert format_value("pass_rate", 0.97) == "97.0%"
    assert format_value("ps49", 0.0123) == "1.2%"


def test_int_formatter():
    assert format_value("n", 12345) == "12,345"
    assert format_value("n_unique_ips", 7) == "7"


def test_inr_formatter_lakh():
    assert "L" in format_value("mean_amt", 250_000)


def test_inr_formatter_crore():
    assert "Cr" in format_value("mean_amt", 25_000_000)


def test_bool_formatter():
    assert format_value("ip_has_mule_ip", 1) == "Yes"
    assert format_value("ip_has_mule_ip", 0) == "No"


def test_normal_band():
    assert normal_band("pass_rate") == "<5%"
    assert normal_band("nonexistent") is None
