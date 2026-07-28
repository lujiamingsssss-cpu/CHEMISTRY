from chemical_trade_copilot.ui_components import build_copy_button_html


def test_copy_button_reads_editable_email_without_injecting_email_html() -> None:
    html = build_copy_button_html()

    assert 'aria-label="Copy English email"' in html
    assert 'textarea[aria-label="Editable English email"]' in html
    assert "navigator.clipboard.writeText(textarea.value)" in html
    assert "{{EMAIL_BODY}}" not in html
