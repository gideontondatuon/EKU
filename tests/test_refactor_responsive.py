"""Render real Django responses with synthetic data in a local browser, no live DB writes."""

from pathlib import Path

import pytest
from django.test import Client
from playwright.sync_api import sync_playwright

from imports.services import smart_import
from publications.services import publish
from tests.test_imports import source_rows, upload, workbook_bytes


@pytest.mark.e2e
@pytest.mark.django_db
@pytest.mark.parametrize("width", [390, 768, 1440])
def test_admin_public_responsive(client, superuser, settings, tmp_path, width):
    settings.MEDIA_ROOT = tmp_path / "uploads"
    batch = smart_import(
        superuser, upload(workbook_bytes(source_rows(account=12345))), is_demo=True
    )
    publish(superuser, "Publikasi sintetis untuk tes tampilan", is_demo=True)
    client.force_login(superuser)
    urls = ["/admin/", "/admin/imports/", f"/admin/imports/{batch.pk}/", "/admin/settings/"]
    pages = {url: client.get(url).content for url in urls}
    pages["/"] = Client().get("/").content
    assert b"BANK SINTETIS" not in pages["/"]
    assert b"12345" not in pages["/"]
    root = Path(__file__).resolve().parents[1]
    output = root / "artifacts" / "refactor-ui"
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as browser_api:
        browser = browser_api.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": width, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def serve(route):
            from urllib.parse import urlparse

            path = urlparse(route.request.url).path
            if path in pages:
                route.fulfill(body=pages[path], content_type="text/html; charset=utf-8")
            elif path.startswith("/static/"):
                import mimetypes

                asset = root / path.lstrip("/")
                if asset.is_file():
                    route.fulfill(
                        body=asset.read_bytes(),
                        content_type=mimetypes.guess_type(asset)[0] or "application/octet-stream",
                    )
                else:
                    route.fulfill(status=404)
            else:
                route.fulfill(status=404)

        page.route("**/*", serve)
        for index, url in enumerate([*urls, "/"]):
            page.goto("http://eku.test" + url)
            page.wait_for_timeout(250)
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), (
                url
            )
            if url == "/admin/imports/":
                assert page.get_by_role("button", name="Unggah & simpan data valid").is_visible()
                if width == 390:
                    page.get_by_role("button", name="Buka navigasi admin").click()
                    page.wait_for_function(
                        "document.querySelector('#admin-sidebar').getBoundingClientRect().left >= 0"
                    )
                    page.keyboard.press("Escape")
                assert page.locator(".sidebar-nav > a").count() == 6
                page.locator("summary").click()
                assert page.locator("#id_mode").is_visible()
                page.locator("summary").click()
            if url == "/":
                assert not page.locator("#id_month").is_visible()
                page.locator("#id_period").select_option("monthly")
                assert page.locator("#id_month").is_visible()
                assert not page.locator("#id_start").is_visible()
                page.locator("#id_period").select_option("custom")
                assert page.get_by_role("link", name="Masuk Admin").is_visible()
                assert page.locator(".tabs").get_by_text("Estimasi", exact=True).count() == 0
            page.screenshot(path=str(output / f"{width}-{index}.png"), full_page=True)
        assert not errors
        browser.close()
