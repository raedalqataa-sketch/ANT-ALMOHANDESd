"""Exercise the real static Pyodide client and verify generated files."""
import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.async_api import async_playwright


async def scenario(browser, base, out, name, country, size, level, floors, family):
    context = await browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
    page = await context.new_page()
    errors, other_origins = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("request", lambda request: other_origins.append(urlsplit(request.url).netloc)
            if urlsplit(request.url).scheme in {"http", "https"} and
            urlsplit(request.url).netloc != urlsplit(base).netloc else None)
    await page.goto(base + "/client/")
    await page.get_by_label("الدولة", exact=True).select_option(country)
    await page.locator('[list="architect-regions"]').fill("الرياض" if country == "SA" else "صنعاء")
    await page.get_by_label("عرض الأرض (م)", exact=True).fill(str(size[0]))
    await page.get_by_label("عمق الأرض (م)", exact=True).fill(str(size[1]))
    if name == "sa-standard":
        await page.screenshot(path=out / "intake.png", full_page=True)
    await page.get_by_role("button", name="التالي", exact=True).click()
    await page.get_by_label("عدد أفراد الأسرة").fill(str(family))
    await page.get_by_label("الأدوار", exact=True).select_option(floors)
    if country == "YE":
        assert await page.get_by_role("checkbox", name="مجلس ضيوف مستقل", exact=False).is_checked()
    await page.get_by_role("button", name="التالي", exact=True).click()
    await page.get_by_label("مستوى المخرجات", exact=True).select_option(level)
    await page.get_by_role("button", name="ولّد البدائل", exact=True).click()
    frame = page.frame_locator("iframe")
    summary = frame.locator("#result-summary")
    await page.wait_for_function("""() => {
      const child = document.querySelector('iframe')?.contentWindow;
      return child?.AntGeneral?.result != null || !!document.querySelector('[role="alert"]');
    }""", timeout=480_000)
    child = page.frames[1]
    result = await child.evaluate("AntGeneral.result")
    passed = [m for m in (result or {}).get("candidates", []) if m["release"]["drawing_export_allowed"]]
    record = {"scenario": name, "passed": len(passed), "unavailable": (result or {}).get("unavailable", [])}
    if name == "failure":
        assert not passed and await frame.locator(".downloads a").count() == 0
        record["message"] = await (summary if result else page.get_by_role("alert")).inner_text()
        if result:
            assert "لم يجد البحث بديلًا" in record["message"]
        else:
            assert record["message"].strip()
    else:
        assert passed, (name, result, errors, await page.get_by_role("alert").all_text_contents())
        assert (result["planning"]["original_intent"]["width"], result["planning"]["original_intent"]["depth"]) == size
        assert result["planning"]["original_intent"]["country"] == country
        assert result["planning"]["original_intent"]["output_level"] == level
        if name == "sa-luxury":
            assert any(len(model["floors"]) == 2 for model in passed)
        assert await frame.locator("#comparison").is_visible() == (len(passed) >= 2)
        accessible_plans = frame.locator("#alternatives button:has(img)")
        assert await accessible_plans.count() == len(passed)
        await frame.locator('[data-floor="GF"]').click()
        await frame.locator('#plan').evaluate('(img) => img.decode()')
        if await frame.locator('[data-floor="FF"]').count():
            await frame.locator('[data-floor="FF"]').click()
        await frame.get_by_role("button", name="تكبير", exact=True).click()
        await frame.get_by_role("button", name="ملاءمة", exact=True).click()
        await frame.get_by_role("button", name="اختيار هذا المقترح", exact=True).click()
        assert await frame.locator("#chosen").is_visible()
        if name == "sa-standard":
            for label, magic in (("↓ PDF", b"%PDF"), ("↓ DXF 2010", b"AC1024"), ("↓ JSON", b"{")):
                async with page.expect_download() as download:
                    await frame.get_by_role("link", name=label, exact=True).click()
                assert magic in Path(await (await download.value).path()).read_bytes()[:4096]
            await frame.locator("#results").screenshot(path=out / "results.png")
            await page.set_viewport_size({"width": 390, "height": 844})
            assert await page.evaluate("document.documentElement.scrollWidth<=innerWidth")
            assert await child.evaluate("document.documentElement.scrollWidth<=innerWidth")
            await page.get_by_role("button", name="عدّل الطلب وأعد التوليد").click()
            assert await page.locator("iframe").count() == 0
            assert await page.get_by_label("عرض الأرض (م)", exact=True).input_value() == str(size[0])
    assert not other_origins and not errors, (other_origins, errors)
    (out / f"{name}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2))
    print(name, len(passed), flush=True)
    await context.close()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8041")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(exist_ok=True, parents=True)
    cases = [
        ("sa-standard", "SA", (24, 32), "standard", "auto", 6),
        ("sa-luxury", "SA", (30, 38), "luxury", "two", 6),
        ("ye-privacy", "YE", (24, 32), "standard", "two", 6),
        ("different-plot", "SA", (22, 28), "economy", "auto", 4),
        ("failure", "SA", (8, 8), "standard", "one", 12),
    ]
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(executable_path="/usr/bin/chromium")
        capacity = asyncio.Semaphore(2)

        async def run(case):
            async with capacity:
                await scenario(browser, args.base, args.out, *case)

        observations = await asyncio.gather(*(run(case) for case in cases), return_exceptions=True)
        await browser.close()
    for case, observation in zip(cases, observations):
        if isinstance(observation, BaseException):
            print(case[0], str(observation)[:3000], flush=True)
    if any(isinstance(observation, BaseException) for observation in observations):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
