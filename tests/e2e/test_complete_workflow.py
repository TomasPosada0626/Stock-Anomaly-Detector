import os
import uuid

import pytest

playwright = pytest.importorskip("playwright.sync_api")
sync_playwright = playwright.sync_playwright


@pytest.mark.skipif(
    os.getenv("RUN_E2E_FULL", "0") != "1",
    reason="Set RUN_E2E_FULL=1 to run complete workflow e2e test.",
)
def test_full_user_workflow() -> None:
    """Test complete workflow: register -> login -> load data -> detect anomalies -> export."""
    base_url = os.getenv("E2E_BASE_URL", "http://127.0.0.1:8501")

    with sync_playwright() as playwright_ctx:
        browser = playwright_ctx.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(base_url, wait_until="domcontentloaded", timeout=120000)

        # Register
        user_id = uuid.uuid4().hex[:8]
        username = f"testuser_{user_id}"
        email = f"test_{user_id}@quantvision.dev"
        password = "TestPass123!@"

        page.get_by_text("Register").first.click()
        page.get_by_label("First Name").fill("Test")
        page.get_by_label("Last Name").fill("User")
        page.get_by_label("Username").fill(username)
        page.get_by_label("Email").fill(email)
        page.get_by_label("Password").first.fill(password)
        page.get_by_label("Repeat Password").fill(password)
        page.get_by_role("button", name="Register").click()

        # Login
        page.wait_for_timeout(1000)
        page.get_by_label("Username or Email").fill(username)
        page.get_by_label("Password").first.fill(password)
        page.get_by_role("button", name="Login").click()

        # Load ticker and verify dashboard
        page.wait_for_timeout(1500)
        page.get_by_role("button", name="Load / Refresh Market Data").click()
        page.wait_for_timeout(3000)
        page.wait_for_function(
            """
            () => {
                const text = (document.body?.innerText || '').toLowerCase();
                return text.includes('dashboard') || text.includes('quantvision');
            }
            """,
            timeout=120000,
        )

        # Go to anomalies and verify export
        page.get_by_text("Anomalies").first.click()
        page.wait_for_timeout(2000)
        page.wait_for_function(
            """
            () => {
                const text = (document.body?.innerText || '').toLowerCase();
                return text.includes('machine learning anomaly detection lab');
            }
            """,
            timeout=120000,
        )

        with page.expect_download(timeout=120000) as download_info:
            page.get_by_role("button", name="Export AAPL anomalies CSV").click()
        download = download_info.value
        assert download.suggested_filename.endswith(".csv")

        page.get_by_role("button", name="Logout").click()
        page.wait_for_function(
            """
            () => {
                const text = (document.body?.innerText || '').toLowerCase();
                return text.includes('login') || text.includes('register');
            }
            """,
            timeout=120000,
        )

        browser.close()
