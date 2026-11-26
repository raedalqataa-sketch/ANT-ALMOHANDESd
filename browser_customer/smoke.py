"""Verify the customer journey against a static server in mobile viewport Chromium."""
import argparse
import re

from playwright.sync_api import expect, sync_playwright


def smoke(base_url, executable):
    with sync_playwright() as tool:
        browser = tool.chromium.launch(
            executable_path=executable,
            args=["--enable-unsafe-swiftshader", "--use-angle=swiftshader"],
        )
        page = browser.new_page(viewport={"width": 390, "height": 844})
        api_requests = []
        page.on("request", lambda request: api_requests.append(request.url) if "/api/" in request.url else None)
        page.set_default_timeout(90_000)
        page.goto(base_url + "/composition/?strategy=clustered")
        page.evaluate("() => window.AntBrowserEngine.prepare()")
        page.locator("#generate").click()
        card = page.locator("#results article").first
        expect(card).to_be_visible(timeout=120_000)
        print("Browser generated a plan", flush=True)
        card.get_by_role("button", name="اختيار هذا المسقط").click()
        card.get_by_role("button", name="تعديل المسقط المقترح").click()
        expect(page).to_have_url(re.compile("/editor/"), timeout=90_000)
        expect(page.locator("#apply-edits")).to_be_enabled(timeout=90_000)
        page.locator("#apply-edits").click()
        expect(page.locator("#options article")).to_have_count(2, timeout=120_000)
        print("Saved plan revision produced two facade options", flush=True)
        page.locator("#options article button").first.click()
        expect(page).to_have_url(re.compile("/massing/"), timeout=90_000)
        expect(page.locator("#workspace")).to_be_visible(timeout=120_000)
        assert not api_requests, api_requests
        print("Plan, editor, facade selection and massing completed without network API calls.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    parser.add_argument("--executable")
    args = parser.parse_args()
    smoke(args.base_url.rstrip("/"), args.executable)
