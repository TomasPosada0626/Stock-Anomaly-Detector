import os

import pytest

playwright = pytest.importorskip("playwright.sync_api")
sync_playwright = playwright.sync_playwright


def test_login_page_smoke() -> None:
    base_url = os.getenv("E2E_BASE_URL", "http://127.0.0.1:8501")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(base_url, wait_until="domcontentloaded", timeout=120000)
        # Streamlit renders app text client-side; wait for body text to appear in CI.
        page.wait_for_function(
            """
            () => {
                const text = (document.body?.innerText || '').toLowerCase();
                return text.includes('login') || text.includes('register') || text.includes('quantvision');
            }
            """,
            timeout=120000,
        )
        content = (page.inner_text("body") or "").lower()
        browser.close()

    assert "login" in content or "quantvision" in content
    assert (
        "you can log in with username or email" in content
        or "username or email" in content
        or "choose action" in content
    )
