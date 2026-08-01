from spotlight.theme import BACKGROUND, BLUE_ACCENT, DARK_STYLESHEET, PINK_ACCENT


def test_dark_theme_contains_the_beep_palette() -> None:
    assert BACKGROUND in DARK_STYLESHEET
    assert BLUE_ACCENT in DARK_STYLESHEET
    assert PINK_ACCENT in DARK_STYLESHEET


def test_dark_theme_styles_the_main_application_regions() -> None:
    for object_name in ("Header", "Sidebar", "Card", "StatusBar"):
        assert f"#{object_name}" in DARK_STYLESHEET
