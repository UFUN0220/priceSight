"""Playwright browser runtime implementing the existing ActionDevice contract.

Playwright is an optional dependency. Importing the backend does not require a
browser installation; launching this runtime produces an explicit dependency
error when the optional extra is absent.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator
from urllib.parse import urlparse

from app.action.matcher import TargetMatch
from app.observation.models import Observation, ObservationNode, PageType

try:  # pragma: no cover - exercised by the optional browser extra
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - normal backend installations do not import it
    Page = Any
    sync_playwright = None

    class PlaywrightError(RuntimeError):  # type: ignore[no-redef]
        """Fallback type used when Playwright is not installed."""

    class PlaywrightTimeoutError(TimeoutError):  # type: ignore[no-redef]
        """Fallback type used when Playwright is not installed."""


_DOM_SNAPSHOT_SCRIPT = r"""
() => {
  const visible = (element) => {
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" &&
      Number(style.opacity || "1") > 0 && rect.width > 0 && rect.height > 0;
  };
  const interactive = (element) => {
    const tag = element.tagName.toLowerCase();
    const role = element.getAttribute("role") || "";
    return ["a", "button", "select", "textarea"].includes(tag) ||
      ["button", "link", "checkbox", "radio", "tab", "option"].includes(role) ||
      element.hasAttribute("onclick") || element.hasAttribute("data-action");
  };
  const editable = (element) => {
    const tag = element.tagName.toLowerCase();
    return tag === "input" || tag === "textarea" || element.isContentEditable;
  };
  const elements = Array.from(document.querySelectorAll("body *"))
    .filter((element) => visible(element) && (interactive(element) || editable(element) ||
      (element.children.length === 0 && (element.innerText || element.textContent || "").trim())));
  const ids = elements.map((_, index) => `browser.node.${index}`);
  const idByElement = new Map(elements.map((element, index) => [element, ids[index]]));
  elements.forEach((element, index) => element.setAttribute("data-pricesight-node-id", ids[index]));
  const parentFor = (element) => {
    let parent = element.parentElement;
    while (parent && !idByElement.has(parent)) parent = parent.parentElement;
    return parent ? idByElement.get(parent) : null;
  };
    const nodes = elements.map((element, index) => {
    const rect = element.getBoundingClientRect();
    const text = (element.innerText || element.textContent || "").trim().replace(/\s+/g, " ");
      const aria = element.getAttribute("aria-label") || element.getAttribute("title");
      const resource = element.getAttribute("data-testid") || element.id || element.getAttribute("name");
    const href = element.tagName.toLowerCase() === "a" ? element.href : null;
    const attributeNames = ["data-item-id", "data-id", "data-seller", "data-shop", "data-sales"];
    const attributes = Object.fromEntries(attributeNames
      .map((name) => [name, element.getAttribute(name)])
      .filter((entry) => entry[1] !== null));
    const children = elements.filter((candidate) => candidate.parentElement === element)
      .map((candidate) => idByElement.get(candidate));
    const style = window.getComputedStyle(element);
    return {
      node_id: ids[index],
      parent_id: parentFor(element),
      class_name: element.tagName.toLowerCase(),
      role: element.getAttribute("role"),
      text: text || null,
      content_description: aria,
      resource_id: resource,
      href: href,
      attributes: attributes,
      clickable: interactive(element),
      editable: editable(element),
      scrollable: element.scrollHeight > element.clientHeight ||
        ["auto", "scroll"].includes(style.overflowY),
      enabled: !element.hasAttribute("disabled"),
      visible: true,
      bounds: [Math.round(rect.left), Math.round(rect.top), Math.round(rect.right), Math.round(rect.bottom)],
      depth: 0,
      children: children,
    };
  });
  return {url: window.location.href, title: document.title, nodes: nodes};
}
"""


@dataclass(frozen=True)
class BrowserObservationParser:
    """Convert a browser DOM snapshot into the project Observation DTO."""

    platform_id: str

    def parse(self, payload: dict[str, Any], observation_id: str) -> Observation:
        nodes = [ObservationNode.model_validate(node) for node in payload.get("nodes", [])]
        url = str(payload.get("url") or "")
        title = str(payload.get("title") or "") or None
        text = " ".join(node.text or "" for node in nodes).casefold()
        return Observation(
            observation_id=observation_id,
            platform=self.platform_id,
            package_name=urlparse(url).hostname,
            page_type=self._page_type(url, title or "", text),
            source_url=url,
            title=title,
            metadata={"runtime": "browser", "platform_id": self.platform_id},
            nodes=nodes,
        )

    @staticmethod
    def _page_type(url: str, title: str, text: str) -> PageType:
        combined = f"{url} {title} {text}".casefold()
        if any(term in combined for term in ("payment", "支付", "checkout", "订单确认")):
            return PageType.CART
        if any(term in combined for term in ("cart", "购物车")):
            return PageType.CART
        if any(term in combined for term in ("search", "搜索")) and "result" not in combined:
            return PageType.SEARCH
        if any(term in combined for term in ("product", "商品详情", "detail")):
            return PageType.PRODUCT
        return PageType.UNKNOWN


class BrowserRuntime:
    """A safe, synchronous browser runtime for local and read-only web tasks."""

    def __init__(
        self,
        page: Page,
        *,
        platform_id: str = "browser",
        allowed_hosts: set[str] | None = None,
        runtime_id: str = "browser-local",
    ) -> None:
        self.page = page
        self.platform_id = platform_id
        self.runtime_id = runtime_id
        current_host = urlparse(page.url).hostname
        self.allowed_hosts = allowed_hosts or ({current_host} if current_host else set())
        self.parser = BrowserObservationParser(platform_id)
        self._observation_sequence = 0
        self.stopped = False

    def observe(self) -> Observation:
        self._assert_allowed_host()
        self._observation_sequence += 1
        payload = self.page.evaluate(_DOM_SNAPSHOT_SCRIPT)
        return self.parser.parse(payload, f"{self.runtime_id}-obs-{self._observation_sequence}")

    def click(self, target: TargetMatch) -> bool:
        try:
            self._locator(target).click(timeout=target_timeout(target))
            return self._navigation_allowed()
        except (PlaywrightTimeoutError, PlaywrightError, ValueError):
            if target.bounds is None:
                return False
            try:
                left, top, right, bottom = target.bounds
                self.page.mouse.click((left + right) / 2, (top + bottom) / 2)
                return self._navigation_allowed()
            except (PlaywrightError, ValueError):
                return False

    def set_text(self, target: TargetMatch, value: str) -> bool:
        try:
            self._locator(target).fill(value, timeout=target_timeout(target))
            return True
        except (PlaywrightError, ValueError):
            return False

    def scroll(self, target: TargetMatch | None, forward: bool) -> bool:
        try:
            if target is not None and target.node_id:
                locator = self._locator(target)
                delta = 700 if forward else -700
                locator.evaluate("(element, delta) => element.scrollBy(0, delta)", delta)
            else:
                self.page.mouse.wheel(0, 700 if forward else -700)
            return True
        except (PlaywrightError, ValueError):
            return False

    def back(self) -> bool:
        try:
            self.page.go_back(wait_until="domcontentloaded", timeout=5000)
            return self._navigation_allowed()
        except (PlaywrightError, ValueError):
            return False

    def wait(self, timeout_ms: int) -> bool:
        try:
            self.page.wait_for_timeout(min(max(timeout_ms, 0), 120000))
            return True
        except (PlaywrightError, ValueError):
            return False

    def stop(self) -> bool:
        self.stopped = True
        return True

    def _locator(self, target: TargetMatch):
        if not target.node_id:
            raise ValueError("browser action requires a node_id or fresh bounds")
        escaped = target.node_id.replace("\\", "\\\\").replace('"', '\\"')
        return self.page.locator(f'[data-pricesight-node-id="{escaped}"]').first

    def _navigation_allowed(self) -> bool:
        try:
            self._assert_allowed_host()
            return True
        except RuntimeError:
            self.stop()
            return False

    def _assert_allowed_host(self) -> None:
        host = urlparse(self.page.url).hostname
        if self.allowed_hosts and host not in self.allowed_hosts:
            raise RuntimeError(f"browser navigation left the allowed host set: {host}")


def target_timeout(target: TargetMatch) -> int:
    """Keep browser locator waits bounded even when a caller supplied stale data."""

    return 3000


@contextmanager
def launch_browser(
    start_url: str,
    *,
    platform_id: str = "browser",
    allowed_hosts: set[str] | None = None,
    headless: bool = True,
    runtime_id: str = "browser-local",
) -> Iterator[BrowserRuntime]:
    """Launch Chromium and yield a BrowserRuntime with an explicit host allowlist."""

    if sync_playwright is None:
        raise RuntimeError(
            "Playwright is not installed; install the optional browser extra and run `playwright install chromium`"
        )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()
        page.goto(start_url, wait_until="domcontentloaded")
        runtime = BrowserRuntime(
            page,
            platform_id=platform_id,
            allowed_hosts=allowed_hosts,
            runtime_id=runtime_id,
        )
        try:
            yield runtime
        finally:
            context.close()
            browser.close()
