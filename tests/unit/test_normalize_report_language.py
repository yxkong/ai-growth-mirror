from ai_growth_mirror.assets.prompts import normalize_report_language


def test_normalize_report_language_defaults_to_zh():
    assert normalize_report_language(None) == "zh"
    assert normalize_report_language("") == "zh"
    assert normalize_report_language("fr") == "zh"


def test_normalize_report_language_accepts_en():
    assert normalize_report_language("en") == "en"
    assert normalize_report_language("zh") == "zh"
