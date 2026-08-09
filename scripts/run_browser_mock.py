"""Run a read-only browser workflow against the local Mock Web app.

The script requires the optional Playwright dependency and Chromium. It never
submits the mock order; the checkout page is inspected only to verify safety.
"""

from __future__ import annotations

import json
import re
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from app.action.executor import ActionExecutor
from app.action.models import ActionRequest, ActionStatus, ActionTarget, ActionType
from app.runtime.browser import launch_browser
from app.task.orchestrator import TaskOrchestrator
from app.workflow.loader import WorkflowLoader
from app.workflow.engine import WorkflowEngine
from app.workflow.models import WorkflowContext, WorkflowStatus


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "mock-shopping-web"
    handler = partial(QuietHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/index.html"
    try:
        with launch_browser(
            url,
            platform_id="mock-web",
            allowed_hosts={"127.0.0.1"},
            headless=True,
        ) as runtime:
            workflow = WorkflowLoader().from_text(
                """
                name: browser_read_only_search
                steps:
                  - id: open_search
                    action: click
                    target: {resource_id: search-button}
                  - id: input_keyword
                    action: set_text
                    target: {resource_id: search-input}
                    value_from: task.product_keyword
                  - id: submit_search
                    action: click
                    target: {resource_id: search-submit}
                  - id: open_product
                    action: click
                    target: {resource_id: product-result-1}
                """
            )
            context = WorkflowContext(
                task_id="browser-mock-read-only",
                goal="搜索可口可乐500ml并读取商品详情",
                task={"product_keyword": "可口可乐500ml"},
            )
            result = TaskOrchestrator(
                WorkflowEngine(action_executor=ActionExecutor())
            ).run(workflow, context, runtime)
            detail = result.final_observation
            price = None
            if detail:
                text = " ".join(node.text or "" for node in detail.nodes)
                match = re.search(r"¥\s*(\d+(?:\.\d+)?)", text)
                price = match.group(1) if match else None

            checkout_result = ActionExecutor().execute(
                ActionRequest(
                    action_type=ActionType.CLICK,
                    target=ActionTarget(resource_id="checkout"),
                    observation_id=detail.observation_id if detail else None,
                ),
                detail,
                runtime,
            ) if detail else None
            safety_observation = runtime.observe()
            safety_result = ActionExecutor().execute(
                ActionRequest(
                    action_type=ActionType.CLICK,
                    target=ActionTarget(resource_id="submit-order"),
                    observation_id=safety_observation.observation_id,
                ),
                safety_observation,
                runtime,
            )
            blocked = safety_result.status is ActionStatus.SAFETY_BLOCKED
            payload = {
                "task_id": context.task_id,
                "status": result.status.value,
                "price": price,
                "checkout_navigation": checkout_result.status.value if checkout_result else None,
                "safety_page_visible": blocked,
                "safety_status": safety_result.status.value,
                "order_was_submitted": False,
                "steps": context.step_count,
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            if (
                result.status is not WorkflowStatus.SUCCEEDED
                or price != "10.90"
                or checkout_result is None
                or not checkout_result.success
                or not blocked
            ):
                raise SystemExit(1)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
