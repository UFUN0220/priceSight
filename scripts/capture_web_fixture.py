"""Capture one sanitized browser Observation fixture.

This tool is intentionally read-only. It never saves browser auth state,
cookies, screenshots, or raw HTML.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from app.platform.web.evidence import evidence_for, sanitize_observation
from app.runtime.browser import launch_browser


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("start_url")
    parser.add_argument("output", type=Path)
    parser.add_argument("--platform-id", required=True)
    parser.add_argument("--allowed-host", required=True)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="headed mode: pause for manual navigation before capture",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output if args.output.is_absolute() else root / args.output
    output = output.resolve()
    if not output.is_relative_to(root):
        raise SystemExit("fixture output must stay under the PriceSight project directory")
    if urlsplit(args.start_url).hostname != args.allowed_host:
        raise SystemExit("start_url hostname must match --allowed-host")
    if args.interactive and not args.headed:
        raise SystemExit("--interactive requires --headed")

    output.parent.mkdir(parents=True, exist_ok=True)
    with launch_browser(
        args.start_url,
        platform_id=args.platform_id,
        allowed_hosts={args.allowed_host},
        headless=not args.headed,
        runtime_id=f"capture-{args.platform_id}",
    ) as runtime:
        if args.interactive:
            input("请在浏览器中完成只读导航后按 Enter 采集；遇到 CAPTCHA/支付/订单页面请停止：")
        observation = sanitize_observation(runtime.observe())
        payload = {
            "observation": observation.model_dump(mode="json"),
            "evidence": evidence_for(observation, args.platform_id).model_dump(mode="json"),
        }
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(output)


if __name__ == "__main__":
    main()
