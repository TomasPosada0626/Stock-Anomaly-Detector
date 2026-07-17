import os

import pytest

playwright = pytest.importorskip("playwright.sync_api")
sync_playwright = playwright.sync_playwright


@pytest.mark.skipif(
    os.getenv("RUN_E2E_FULL", "0") != "1",
    reason="Set RUN_E2E_FULL=1 to run full workflow e2e test.",
)
def test_full_workflow_login_load_detect_export() -> None:
    base_url = os.getenv("E2E_BASE_URL", "http://127.0.0.1:8501")

    username = os.getenv("E2E_USER", "")
    password = os.getenv("E2E_PASSWORD", "")
    if not username or not password:
        pytest.skip("E2E_USER and E2E_PASSWORD are required for full workflow test.")

    with sync_playwright() as playwright_ctx:
        browser = playwright_ctx.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(base_url, wait_until="domcontentloaded", timeout=120000)

        page.get_by_label("Username or Email").fill(username)
        page.get_by_label("Password").fill(password)
        page.get_by_role("button", name="Login").click()

        page.wait_for_timeout(1500)
        page.wait_for_function(
            """
            () => {
                const text = (document.body?.innerText || '').toLowerCase();
                return text.includes('workspace') || text.includes('dashboard') || text.includes('quantvision');
            }
            """,
            timeout=120000,
        )

        # Load data from sidebar controls.
        load_button = page.get_by_role("button", name="Load / Refresh Market Data")
        load_button.click()
        page.wait_for_timeout(2000)

        # Open anomalies workspace.
        page.get_by_text("Anomalies").first.click()
        page.wait_for_timeout(1000)

        page.wait_for_function(
            """
            () => {
                const text = (document.body?.innerText || '').toLowerCase();
                return text.includes('machine learning anomaly detection lab');
            }
            """,
            timeout=120000,
        )

        # Trigger CSV export and assert a download is produced.
        with page.expect_download(timeout=120000) as download_info:
            page.get_by_role("button", name="Export AAPL anomalies CSV").click()
        download = download_info.value

        assert download.suggested_filename.endswith(".csv")
        browser.close()
