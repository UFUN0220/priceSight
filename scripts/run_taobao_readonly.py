"""Run a bounded, read-only Taobao BrowserRuntime smoke test.

The runner performs no login, typing, clicking, cart mutation, checkout, or
payment action. It opens one explicitly allowlisted URL, reads the DOM/ARIA
observation, classifies page state, and extracts visible product evidence.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from app.platform.taobao import (
    TAOBAO_ALLOWED_HOSTS,
    TaobaoPageState,
    TaobaoPlatformAdapter,
)
from app.runtime.browser import launch_browser


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = "https://uland.taobao.com/sem/tbsearch?q=iphone17"
DEFAULT_REPORT = ROOT / "evaluation" / "reports" / "taobao_live_readonly_validation.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-url", default=DEFAULT_URL)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--headed", action="store_true")
    return parser.parse_args()


def _report_path(path: Path) -> Path:
    resolved = path if path.is_absolute() else ROOT / path
    resolved = resolved.resolve()
    if not resolved.is_relative_to(ROOT):
        raise SystemExit("report output must stay under the PriceSight project directory")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def _base_report(start_url: str) -> dict[str, object]:
    parsed = urlsplit(start_url)
    query = parse_qs(parsed.query).get("q", [None])[0]
    return {
        "test_date": datetime.now(timezone.utc).isoformat(),
        "environment": "Playwright Chromium through BrowserRuntime",
        "browser": "Chromium",
        "query": query,
        "start_url_host": parsed.hostname,
        "real_page_accessed": False,
        "host_verified": parsed.hostname in TAOBAO_ALLOWED_HOSTS,
        "login_required": False,
        "captcha_detected": False,
        "page_state": TaobaoPageState.UNKNOWN.value,
        "observation_generated": False,
        "items_extracted": 0,
        "selector_strategy": {},
        "selector_fallback_used": False,
        "displayed_price_extracted": 0,
        "product_url_extracted": 0,
        "external_side_effect": False,
        "fixture_regression_result": "run_separately",
        "backend_test_result": "run_separately",
        "browser_test_result": "run_separately",
        "mock_e2e_result": "run_separately",
        "failures": [],
        "limitations": [
            "本 runner 只读取当前公开页面，不执行登录、点击、输入、加购、下单或支付。",
            "实时页面结果不得与 fixture 或 Mock 结果混合统计。",
        ],
        "status": "NOT_VERIFIED",
    }


def run(start_url: str, *, headed: bool) -> dict[str, object]:
    report = _base_report(start_url)
    if not report["host_verified"]:
        report["status"] = "BLOCKED"
        report["failures"] = ["start URL host is not in the Taobao allowlist"]
        return report

    adapter = TaobaoPlatformAdapter()
    try:
        with launch_browser(
            start_url,
            platform_id="taobao",
            allowed_hosts=set(TAOBAO_ALLOWED_HOSTS),
            headless=not headed,
            runtime_id="taobao-live-readonly",
        ) as runtime:
            observation = runtime.observe()
            assessment = adapter.assess_page(observation)
            report["real_page_accessed"] = True
            report["host_verified"] = assessment.host_verified
            report["observation_generated"] = True
            report["page_state"] = assessment.state.value
            report["login_required"] = assessment.state is TaobaoPageState.LOGIN_REQUIRED
            report["captcha_detected"] = assessment.state is TaobaoPageState.RISK_BLOCKED

            if assessment.state is TaobaoPageState.LOADING:
                runtime.wait(1000)
                observation = runtime.observe()
                assessment = adapter.assess_page(observation)
                report["page_state"] = assessment.state.value

            if assessment.state in {
                TaobaoPageState.LOGIN_REQUIRED,
                TaobaoPageState.RISK_BLOCKED,
                TaobaoPageState.POPUP,
                TaobaoPageState.LOADING,
            }:
                report["status"] = "BLOCKED"
                report["failures"] = [assessment.reason]
                return report

            extraction = adapter.extract_products(observation)
            report["items_extracted"] = len(extraction.products)
            report["selector_strategy"] = extraction.selector_strategy
            report["selector_fallback_used"] = any(
                level > 1 for level in extraction.selector_fallback_level.values()
            )
            report["displayed_price_extracted"] = sum(
                product.displayed_price is not None for product in extraction.products
            )
            report["product_url_extracted"] = sum(
                bool(product.product_url) for product in extraction.products
            )
            if extraction.recognized:
                report["status"] = "LIVE_READONLY_VERIFIED"
            else:
                report["status"] = "NOT_VERIFIED"
                report["failures"] = [extraction.failure_reason or "Taobao products were not recognized"]
    except Exception as exc:  # noqa: BLE001 - runner must emit a bounded report
        report["status"] = "BLOCKED"
        report["failures"] = [f"{type(exc).__name__}: live browser access did not complete"]
    return report


def main() -> None:
    args = parse_args()
    report = run(args.start_url, headed=args.headed)
    output = _report_path(args.report)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
