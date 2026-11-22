"""Browser adapter for the local fictional case. Captures visible DOM and screenshots."""
import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("home")
    sub.add_parser("search").add_argument("query")
    sub.add_parser("open").add_argument("record")
    args = parser.parse_args()
    origin = (ROOT / ".mock-origin").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"http://127\.0\.0\.1:\d+", origin):
        parser.error("The browser can only access the local mock server.")
    if args.action == "open" and not re.fullmatch(r"[A-Z]{3,4}-\d{3}", args.record):
        parser.error("Expected a record ID from the workspace.")
    trace_dir = ROOT / "trace"
    trace_dir.mkdir(exist_ok=True)
    journal = trace_dir / "browser.jsonl"
    number = 1 + (len(journal.read_text(encoding="utf-8").splitlines()) if journal.exists() else 0)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("C06_CHROMIUM") or None,
            args=["--disable-background-networking"],
        )
        page = browser.new_page(viewport={"width": 1120, "height": 700}, locale="zh-CN")
        page.route("**/*", lambda route: route.continue_()
                   if route.request.url.startswith(origin + "/") else route.abort())
        page.goto(origin + "/")
        page.locator("main h1").wait_for()
        if args.action == "search":
            page.get_by_role("textbox", name="企业名称").fill(args.query)
            page.get_by_role("button", name="查询").click()
            page.get_by_role("heading", name="企业查询结果").wait_for()
        if args.action == "open":
            link = page.locator("[data-record='" + args.record + "']")
            if not link.count():
                parser.error("Record not listed on the workspace home page.")
            link.click(timeout=4000)
            page.locator("#record-detail").wait_for()
        main_view = page.locator("main")
        screenshot = f"step-{number:02}.png"
        page.screenshot(path=trace_dir / screenshot, animations="disabled")
        event = {
            "action": args.action,
            "query": getattr(args, "query", None),
            "record": getattr(args, "record", None),
            "path": page.url.removeprefix(origin),
            "title": main_view.locator("h1").inner_text(),
            "text": main_view.inner_text(),
            "screenshot": screenshot,
            "capturedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        browser.close()
    with journal.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")
    print(f"本地模拟网页 {event['path']}\n{event['text']}")


if __name__ == "__main__":
    main()

