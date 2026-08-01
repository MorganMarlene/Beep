def test_application_module_can_be_imported() -> None:
    import spotlight.app  # noqa: F401, PLC0415


def test_application_brand_name_is_beep() -> None:
    from spotlight.app import APPLICATION_NAME

    assert APPLICATION_NAME == "BEEP"
