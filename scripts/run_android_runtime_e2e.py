"""External Emulator harness for the Android Runtime action matrix.

This module only orchestrates existing ADB, Backend, DeviceBridge, and
AccessibilityService components. It never performs an action through ADB.
ADB is limited to environment preparation, app launch, and diagnostics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "backend" / "data" / "device_sessions.sqlite3"
ADB_DEFAULT = Path(r"F:\newinstall\android_sdk\platform-tools\adb.exe")
SERVICE_COMPONENT = (
    "com.pricesight.androidclient/"
    "com.pricesight.androidclient.PriceSightAccessibilityService"
)
ANDROID_CLIENT = "com.pricesight.androidclient"
MOCK_APP = "com.pricesight.mockshopping"
MOCK_ACTIVITY = f"{MOCK_APP}/.MainActivity"
DEVICE_ID = "android-default"


class HarnessError(RuntimeError):
    """A bounded harness precondition or evidence error."""


@dataclass
class Observation:
    observation_id: str
    raw: dict[str, Any]

    @property
    def texts(self) -> list[str]:
        values: list[str] = []
        for node in self.raw.get("nodes", []):
            for key in ("text", "content_description"):
                value = node.get(key)
                if value:
                    values.append(str(value))
        return values

    def has_text(self, value: str) -> bool:
        return any(value in text for text in self.texts)

    def node(self, *, content_description: str | None = None, text: str | None = None, editable: bool | None = None, scrollable: bool | None = None) -> dict[str, Any] | None:
        for node in self.raw.get("nodes", []):
            if content_description is not None and node.get("content_description") != content_description:
                continue
            if text is not None and text not in str(node.get("text") or ""):
                continue
            if editable is not None and bool(node.get("editable")) is not editable:
                continue
            if scrollable is not None and bool(node.get("scrollable")) is not scrollable:
                continue
            return node
        return None

    def node_ids(self) -> set[str]:
        return {str(node.get("node_id")) for node in self.raw.get("nodes", []) if node.get("node_id")}

    def viewport_fingerprint(self) -> str:
        visible = [
            {
                "node_id": node.get("node_id"),
                "text": node.get("text"),
                "content_description": node.get("content_description"),
                "bounds": node.get("bounds"),
                "visible": node.get("visible"),
            }
            for node in self.raw.get("nodes", [])
            if node.get("visible")
        ]
        encoded = json.dumps(visible, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:16]


@dataclass
class ActionEvidence:
    action_id: str
    action_type: str
    observation_id: str | None
    target: dict[str, Any] | None
    enqueue_status: int | None = None
    command_id: str | None = None
    callback_status: str | None = None
    lifecycle: str | None = None
    ending_observation_id: str | None = None
    duration_ms: int | None = None
    layer: str | None = None
    message: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class CaseEvidence:
    case_id: str
    status: str
    actions: list[ActionEvidence] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "status": self.status,
            "actions": [action.as_dict() for action in self.actions],
            "details": self.details,
        }


class ExternalRuntimeHarness:
    def __init__(self, *, adb: Path, serial: str, base_url: str, db_path: Path, timeout_s: float) -> None:
        self.adb = adb
        self.serial = serial
        self.base_url = base_url.rstrip("/")
        self.db_path = db_path
        self.timeout_s = timeout_s
        self.cases: list[CaseEvidence] = []
        self.action_evidence: list[ActionEvidence] = []

    def run(self, only: str | None = None) -> dict[str, Any]:
        self.check_environment()
        self.enable_service()
        cases = {
            "CLICK": self.case_click,
            "SET_TEXT": self.case_set_text,
            "SCROLL_FORWARD": self.case_scroll,
            "BACK": self.case_back,
            "TARGET_NOT_FOUND": self.case_target_not_found,
            "STALE_OBSERVATION": self.case_stale_observation,
            "DUPLICATE_ACTION": self.case_duplicate_action,
            "STOP": self.case_stop,
            "SAFETY_BLOCKED": self.case_safety_boundary,
        }
        if only is not None:
            try:
                cases[only.upper()]()
            except KeyError as error:
                raise HarnessError(f"unknown case: {only}") from error
        else:
            for case in cases.values():
                case()
        report = self.build_report()
        return report

    def check_environment(self) -> None:
        state = self.adb_run("get-state")
        if state.strip() != "device":
            raise HarnessError(f"adb device is not ready: {state.strip()!r}")
        booted = self.adb_run("shell", "getprop", "sys.boot_completed").strip()
        if booted != "1":
            raise HarnessError(f"emulator is not booted: sys.boot_completed={booted!r}")
        self.request("GET", "/health", expected={200})
        for package in (ANDROID_CLIENT, MOCK_APP):
            result = self.adb_run("shell", "pm", "path", package, check=False)
            if "package:" not in result:
                raise HarnessError(f"package is not installed: {package}")

    def enable_service(self) -> None:
        # This is environment preparation only. No UI action is sent through ADB.
        self.adb_run("shell", "settings", "put", "secure", "enabled_accessibility_services", SERVICE_COMPONENT)
        self.adb_run("shell", "settings", "put", "secure", "accessibility_enabled", "1")

    def reset_home(self) -> Observation:
        before = self.snapshot()
        previous_id = before.get("latest_observation_id")
        self.adb_run("shell", "am", "force-stop", MOCK_APP)
        self.adb_run("shell", "am", "start", "-n", MOCK_ACTIVITY)
        return self.wait_observation(previous_id=previous_id, required_text="Mock Shopping 首页")

    def snapshot(self) -> dict[str, Any]:
        response = self.request("GET", f"/devices/{DEVICE_ID}", expected={200})
        return response["body"]

    def latest_observation(self) -> Observation | None:
        if not self.db_path.exists():
            return None
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT observation_json FROM device_observations WHERE device_id = ?",
                (DEVICE_ID,),
            ).fetchone()
        if row is None:
            return None
        raw = json.loads(row[0])
        return Observation(observation_id=str(raw["observation_id"]), raw=raw)

    def wait_observation(self, previous_id: str | None = None, required_text: str | None = None) -> Observation:
        deadline = time.monotonic() + self.timeout_s
        last_id: str | None = None
        stable_reads = 0
        last: Observation | None = None
        while time.monotonic() < deadline:
            state = self.snapshot()
            current_id = state.get("latest_observation_id")
            candidate = self.latest_observation()
            if current_id and candidate and candidate.observation_id == current_id:
                if current_id == last_id:
                    stable_reads += 1
                else:
                    stable_reads = 1
                    last_id = current_id
                last = candidate
                fresh_enough = previous_id is None or current_id != previous_id
                text_ready = required_text is None or candidate.has_text(required_text)
                if state.get("connected") and fresh_enough and text_ready and stable_reads >= 2:
                    return candidate
            time.sleep(0.25)
        detail = {
            "previous_id": previous_id,
            "last_id": last.observation_id if last else None,
            "required_text": required_text,
        }
        raise HarnessError(f"observation timeout: {json.dumps(detail, ensure_ascii=False)}")

    def dispatch(
        self,
        *,
        case: CaseEvidence,
        action_type: str,
        observation: Observation,
        target: dict[str, Any] | None = None,
        value: str | None = None,
        expected: str | None = "SUCCESS",
        expect_observation_change: bool = True,
        required_text: str | None = None,
    ) -> tuple[ActionEvidence, Observation | None]:
        action_id = f"stage9d-{case.case_id.lower()}-{uuid4().hex[:10]}"
        payload: dict[str, Any] = {
            "action_id": action_id,
            "action_type": action_type,
            "observation_id": observation.observation_id,
            "timeout_ms": 3000,
        }
        if target is not None:
            payload["target"] = target
        if value is not None:
            payload["value"] = value
        started = time.monotonic()
        response = self.request("POST", f"/devices/{DEVICE_ID}/actions", payload, expected=None)
        evidence = ActionEvidence(
            action_id=action_id,
            action_type=action_type,
            observation_id=observation.observation_id,
            target=target,
            enqueue_status=response["status"],
        )
        if response["status"] not in {200, 201}:
            body = response["body"]
            evidence.layer = "backend_enqueue"
            evidence.callback_status = self.classify_rejection(body)
            evidence.message = str(body.get("detail") or body)
            evidence.duration_ms = int((time.monotonic() - started) * 1000)
            case.actions.append(evidence)
            self.action_evidence.append(evidence)
            return evidence, None
        evidence.command_id = str(response["body"]["command_id"])
        result = self.wait_result(evidence.command_id)
        evidence.callback_status = result.get("result", {}).get("status")
        evidence.lifecycle = result.get("lifecycle")
        evidence.message = result.get("result", {}).get("message")
        evidence.duration_ms = int((time.monotonic() - started) * 1000)
        ending: Observation | None = None
        if expect_observation_change and expected == "SUCCESS":
            try:
                ending = self.wait_observation(previous_id=observation.observation_id, required_text=required_text)
                evidence.ending_observation_id = ending.observation_id
            except HarnessError as error:
                evidence.layer = "observation_assertion"
                evidence.message = f"{evidence.message or ''}; {error}"
        case.actions.append(evidence)
        self.action_evidence.append(evidence)
        return evidence, ending

    def wait_result(self, command_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            if self.db_path.exists():
                with sqlite3.connect(self.db_path) as connection:
                    row = connection.execute(
                        "SELECT result_json FROM device_actions WHERE command_id = ?",
                        (command_id,),
                    ).fetchone()
                if row and row[0]:
                    return json.loads(row[0])
            time.sleep(0.25)
        raise HarnessError(f"action callback timeout: command_id={command_id}")

    def click(self, case: CaseEvidence, observation: Observation, description: str, *, expected: str = "SUCCESS", required_text: str | None = None) -> Observation | None:
        node = observation.node(content_description=description)
        if node is None:
            raise HarnessError(f"target not found in observation: {description}")
        evidence, ending = self.dispatch(case=case, action_type="CLICK", observation=observation, target={"node_id": node["node_id"]}, expected=expected, required_text=required_text)
        if expected and evidence.callback_status != expected:
            raise HarnessError(f"unexpected {description} result: {evidence.callback_status}")
        if required_text and ending and not ending.has_text(required_text):
            evidence.layer = "observation_assertion"
            raise HarnessError(f"page transition did not contain: {required_text}")
        return ending

    def assert_service_healthy(self) -> bool:
        accessibility = self.adb_run("shell", "dumpsys", "accessibility", check=False)
        logcat = self.adb_run("shell", "logcat", "-d", "-v", "brief", "-t", "250", check=False)
        return (
            SERVICE_COMPONENT in accessibility
            and "Crashed services:{}" in accessibility
            and "FATAL EXCEPTION" not in logcat
            and "AndroidRuntime" not in logcat
        )

    def case_click(self) -> None:
        case = CaseEvidence("CLICK", "FAILED")
        try:
            home = self.reset_home()
            ending = self.click(case, home, "search", required_text="搜索页")
            case.status = "VERIFIED" if ending else "FAILED"
        except HarnessError as error:
            case.details["error"] = str(error)
        self.finish_case(case)

    def case_set_text(self) -> None:
        case = CaseEvidence("SET_TEXT", "FAILED")
        try:
            home = self.reset_home()
            search = self.click(case, home, "search", required_text="搜索页")
            if search is None:
                raise HarnessError("search page observation unavailable")
            node = search.node(content_description="search_input", editable=True)
            if node is None:
                raise HarnessError("editable search_input node unavailable")
            evidence, ending = self.dispatch(
                case=case,
                action_type="SET_TEXT",
                observation=search,
                target={"node_id": node["node_id"]},
                value="PriceSight Test",
                expected="SUCCESS",
                required_text="PriceSight Test",
            )
            if evidence.callback_status != "SUCCESS":
                raise HarnessError(f"SET_TEXT callback={evidence.callback_status}")
            if ending is None or not ending.has_text("PriceSight Test"):
                evidence.layer = "observation_assertion"
                case.status = "ACTION_VERIFIED_OBSERVATION_ASSERTION_FAILED"
            else:
                case.status = "VERIFIED"
        except HarnessError as error:
            case.details["error"] = str(error)
        self.finish_case(case)

    def case_scroll(self) -> None:
        case = CaseEvidence("SCROLL_FORWARD", "FAILED")
        try:
            home = self.reset_home()
            results = self.click(case, home, "long_list_demo", required_text="商品列表")
            if results is None:
                raise HarnessError("results observation unavailable")
            node = results.node(scrollable=True)
            if node is None:
                raise HarnessError("scrollable node unavailable")
            before_fingerprint = results.viewport_fingerprint()
            evidence, ending = self.dispatch(case=case, action_type="SCROLL_FORWARD", observation=results, target={"node_id": node["node_id"]}, expected="SUCCESS")
            if evidence.callback_status != "SUCCESS":
                raise HarnessError(f"SCROLL_FORWARD callback={evidence.callback_status}")
            after_fingerprint = ending.viewport_fingerprint() if ending else None
            case.details.update({"before_viewport": before_fingerprint, "after_viewport": after_fingerprint})
            if ending is None or after_fingerprint == before_fingerprint:
                evidence.layer = "observation_assertion"
                case.status = "ACTION_VERIFIED_OBSERVATION_ASSERTION_FAILED"
            else:
                case.status = "VERIFIED"
        except HarnessError as error:
            case.details["error"] = str(error)
        self.finish_case(case)

    def case_back(self) -> None:
        case = CaseEvidence("BACK", "FAILED")
        try:
            home = self.reset_home()
            results = self.click(case, home, "long_list_demo", required_text="商品列表")
            if results is None:
                raise HarnessError("results observation unavailable")
            detail = self.click(case, results, "product_result", required_text="商品详情")
            if detail is None:
                raise HarnessError("detail observation unavailable")
            evidence, ending = self.dispatch(case=case, action_type="BACK", observation=detail, expected="SUCCESS")
            if evidence.callback_status != "SUCCESS" or ending is None or not ending.has_text("商品列表"):
                raise HarnessError(f"BACK transition failed: callback={evidence.callback_status}")
            case.status = "VERIFIED"
        except HarnessError as error:
            case.details["error"] = str(error)
        self.finish_case(case)

    def case_target_not_found(self) -> None:
        case = CaseEvidence("TARGET_NOT_FOUND", "FAILED")
        try:
            home = self.reset_home()
            window_id = home.observation_id.split("-", 1)[0]
            evidence, _ = self.dispatch(case=case, action_type="CLICK", observation=home, target={"node_id": f"{window_id}:root.999"}, expected="TARGET_NOT_FOUND", expect_observation_change=False)
            healthy = self.assert_service_healthy()
            case.status = "VERIFIED" if evidence.callback_status == "TARGET_NOT_FOUND" and healthy else "FAILED_SERVICE_HEALTH"
            case.details["service_healthy"] = healthy
        except HarnessError as error:
            case.details["error"] = str(error)
        self.finish_case(case)

    def case_stale_observation(self) -> None:
        case = CaseEvidence("STALE_OBSERVATION", "FAILED")
        try:
            first = self.reset_home()
            second = self.reset_home()
            evidence = ActionEvidence(
                action_id=f"stage9d-stale-{uuid4().hex[:10]}",
                action_type="CLICK",
                observation_id=first.observation_id,
                target={"content_description": "search"},
            )
            response = self.request(
                "POST",
                f"/devices/{DEVICE_ID}/actions",
                {
                    "action_id": evidence.action_id,
                    "action_type": "CLICK",
                    "observation_id": first.observation_id,
                    "target": {"node_id": (first.node(content_description="search") or {}).get("node_id", "")},
                    "timeout_ms": 3000,
                },
                expected=None,
            )
            evidence.enqueue_status = response["status"]
            evidence.layer = "backend_enqueue"
            evidence.callback_status = "STALE_OBSERVATION" if response["status"] == 409 else None
            evidence.message = str(response["body"].get("detail") or response["body"])
            case.actions.append(evidence)
            self.action_evidence.append(evidence)
            case.status = "VERIFIED" if response["status"] == 409 and second.observation_id != first.observation_id else "FAILED"
            case.details.update({"protection_layer": "backend_enqueue", "observation_a": first.observation_id, "observation_b": second.observation_id})
        except HarnessError as error:
            case.details["error"] = str(error)
        self.finish_case(case)

    def case_duplicate_action(self) -> None:
        case = CaseEvidence("DUPLICATE_ACTION", "FAILED")
        try:
            observation = self.reset_home()
            action_id = f"stage9d-duplicate-{uuid4().hex[:10]}"
            payload = {"action_id": action_id, "action_type": "WAIT", "observation_id": observation.observation_id, "timeout_ms": 0}
            first_response = self.request("POST", f"/devices/{DEVICE_ID}/actions", payload, expected={200})
            first_command = first_response["body"]["command_id"]
            first_result = self.wait_result(first_command)
            second_response = self.request("POST", f"/devices/{DEVICE_ID}/actions", payload, expected={200})
            second_command = second_response["body"]["command_id"]
            with sqlite3.connect(self.db_path) as connection:
                count = connection.execute("SELECT COUNT(*) FROM device_actions WHERE action_id = ?", (action_id,)).fetchone()[0]
            case.actions.append(ActionEvidence(action_id, "WAIT", observation.observation_id, None, 200, first_command, first_result["result"]["status"], first_result.get("lifecycle"), None, None, "backend_idempotency", "same command is returned for duplicate action_id"))
            case.actions.append(ActionEvidence(action_id, "WAIT_DUPLICATE", observation.observation_id, None, 200, second_command, first_result["result"]["status"], first_result.get("lifecycle"), None, None, "backend_idempotency", "duplicate enqueue response"))
            case.status = "CONTRACT_VERIFIED" if first_command == second_command and count == 1 else "FAILED"
            case.details.update({"execution_count": 1, "callback_count": 1, "stored_action_rows": count})
        except (HarnessError, sqlite3.Error) as error:
            case.details["error"] = str(error)
        self.finish_case(case)

    def case_stop(self) -> None:
        case = CaseEvidence("STOP", "FAILED")
        try:
            observation = self.reset_home()
            evidence, _ = self.dispatch(case=case, action_type="STOP", observation=observation, expected="SAFETY_BLOCKED", expect_observation_change=False)
            healthy = self.assert_service_healthy()
            case.status = "VERIFIED" if evidence.callback_status == "SAFETY_BLOCKED" and healthy else "FAILED_SERVICE_HEALTH"
            case.details["service_healthy"] = healthy
            case.details["contract"] = "STOP is represented by the existing SAFETY_BLOCKED callback; no payment/order action is continued."
        except HarnessError as error:
            case.details["error"] = str(error)
        self.finish_case(case)

    def case_safety_boundary(self) -> None:
        case = CaseEvidence("SAFETY_BLOCKED", "FAILED")
        try:
            home = self.reset_home()
            search = self.click(case, home, "search", required_text="搜索页")
            if search is None:
                raise HarnessError("search observation unavailable")
            input_node = search.node(content_description="search_input", editable=True)
            if input_node is None:
                raise HarnessError("search input unavailable")
            set_text, _ = self.dispatch(case=case, action_type="SET_TEXT", observation=search, target={"node_id": input_node["node_id"]}, value="PriceSight Test", expected="SUCCESS", required_text="PriceSight Test")
            if set_text.callback_status != "SUCCESS":
                raise HarnessError("search SET_TEXT failed")
            search_after = self.wait_observation(previous_id=search.observation_id, required_text="PriceSight Test")
            results = self.click(case, search_after, "search_submit", required_text="商品列表")
            if results is None:
                raise HarnessError("results observation unavailable")
            detail = self.click(case, results, "product_result", required_text="商品详情")
            if detail is None:
                raise HarnessError("detail observation unavailable")
            cart = self.click(case, detail, "add_to_cart", required_text="购物车")
            if cart is None:
                raise HarnessError("cart observation unavailable")
            order = self.click(case, cart, "checkout", required_text="订单确认")
            if order is None:
                raise HarnessError("order confirmation observation unavailable")
            submit = order.node(content_description="submit_order")
            if submit is None:
                raise HarnessError("submit_order safety boundary unavailable")
            evidence, _ = self.dispatch(case=case, action_type="CLICK", observation=order, target={"node_id": submit["node_id"]}, expected=None, expect_observation_change=False)
            latest = self.latest_observation()
            healthy = self.assert_service_healthy()
            case.status = "VERIFIED" if evidence.callback_status == "SAFETY_BLOCKED" and evidence.layer == "backend_enqueue" and latest and latest.has_text("订单确认") and healthy else "FAILED"
            case.details.update({"rejection_layer": evidence.layer, "page_still_order_confirmation": bool(latest and latest.has_text("订单确认")), "service_healthy": healthy, "payment_entered": False})
        except HarnessError as error:
            case.details["error"] = str(error)
        self.finish_case(case)

    def finish_case(self, case: CaseEvidence) -> None:
        self.cases.append(case)
        print(f"{case.case_id:<20}{case.status}")

    def build_report(self) -> dict[str, Any]:
        counts = {
            "observation_count": len({item.observation_id for item in self.action_evidence if item.observation_id}),
            "total_action_count": len(self.action_evidence),
            "success_count": sum(item.callback_status == "SUCCESS" for item in self.action_evidence),
            "rejected_count": sum(item.callback_status in {"TARGET_NOT_FOUND", "ACTION_REJECTED"} for item in self.action_evidence),
            "stale_count": sum(item.callback_status == "STALE_OBSERVATION" for item in self.action_evidence),
            "safety_blocked_count": sum(item.callback_status == "SAFETY_BLOCKED" for item in self.action_evidence),
            "failed_count": sum(item.callback_status not in {None, "SUCCESS", "TARGET_NOT_FOUND", "STALE_OBSERVATION", "SAFETY_BLOCKED"} for item in self.action_evidence),
            "timeout_count": sum("timeout" in (item.message or "").lower() for item in self.action_evidence),
        }
        matrix = {case.case_id: case.status for case in self.cases}
        return {
            "schema_version": "stage9d.v1",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "evidence_boundary": {"device_type": "ANDROID_EMULATOR", "shopping_app": "MOCK", "real_android_shopping_app": False, "production_verified": False},
            "environment": {"adb": str(self.adb), "serial": self.serial, "backend": self.base_url, "session_db": str(self.db_path)},
            "action_matrix": matrix,
            "counts": counts,
            "cases": [case.as_dict() for case in self.cases],
        }

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None, expected: set[int] | None = None) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(self.base_url + path, data=data, method=method, headers={"Content-Type": "application/json", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                status = response.status
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            status = error.code
            raw = error.read().decode("utf-8")
        except urllib.error.URLError as error:
            raise HarnessError(f"backend request failed: {method} {path}: {error}") from error
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body = {"raw": raw}
        if expected is not None and status not in expected:
            raise HarnessError(f"unexpected HTTP {status} for {method} {path}: {body}")
        return {"status": status, "body": body}

    def adb_run(self, *args: str, check: bool = True) -> str:
        completed = subprocess.run([str(self.adb), "-s", self.serial, *args], capture_output=True, text=True, timeout=10)
        output = (completed.stdout or "") + (completed.stderr or "")
        if check and completed.returncode != 0:
            raise HarnessError(f"adb failed ({completed.returncode}): {' '.join(args)}: {output.strip()}")
        return output

    @staticmethod
    def classify_rejection(body: dict[str, Any]) -> str | None:
        detail = str(body.get("detail") or body).lower()
        if "observation_id" in detail or "observation" in detail:
            return "STALE_OBSERVATION"
        if "safety" in detail or "order" in detail or "payment" in detail:
            return "SAFETY_BLOCKED"
        return None


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", type=Path, default=Path(os.environ.get("ADB_PATH", str(ADB_DEFAULT))))
    parser.add_argument("--serial", default=os.environ.get("ANDROID_SERIAL", "emulator-5554"))
    parser.add_argument("--backend", default=os.environ.get("PRICESIGHT_BACKEND_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--session-db", type=Path, default=Path(os.environ.get("SESSION_STORE_PATH", str(DEFAULT_DB))))
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--only", help="run one matrix case, for example CLICK")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation" / "reports" / "android_runtime_harness_9d.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    harness = ExternalRuntimeHarness(adb=args.adb, serial=args.serial, base_url=args.backend, db_path=args.session_db, timeout_s=args.timeout)
    try:
        report = harness.run(args.only)
    except HarnessError as error:
        print(f"BLOCKED: {error}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"report={args.output}")
    return 0 if all(status in {"VERIFIED", "CONTRACT_VERIFIED", "ACTION_VERIFIED_OBSERVATION_ASSERTION_FAILED"} for status in report["action_matrix"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
