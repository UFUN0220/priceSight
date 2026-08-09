"""Deterministic mock-shopping device used by repeatable phase 8 E2E tests."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from app.action.fake import FakeActionCall
from app.action.matcher import TargetMatch
from app.observation.compressor import CompressionStats, ObservationCompressor
from app.observation.models import Observation, ObservationNode, PageType


class MockPage(StrEnum):
    HOME = "home"
    SEARCH = "search"
    RESULTS = "results"
    DETAIL = "detail"
    SPEC_DIALOG = "spec_dialog"
    COUPONS = "coupons"
    CART = "cart"
    ORDER_CONFIRM = "order_confirm"
    PAYMENT = "payment"


class MockShoppingState(BaseModel):
    page: MockPage = MockPage.HOME
    query: str = ""
    selected_product: str | None = None
    selected_spec: str | None = None
    coupon_claimed: bool = False
    cart_quantity: int = 0
    loaded_results: int = Field(default=10, ge=1)
    revision: int = Field(default=0, ge=0)


class MockShoppingDevice:
    """ActionDevice implementation that emits raw trees and compresses every observation."""

    def __init__(self, compressor: ObservationCompressor | None = None) -> None:
        self.state = MockShoppingState()
        self.compressor = compressor or ObservationCompressor()
        self.calls: list[FakeActionCall] = []
        self.compression_stats: list[CompressionStats] = []
        self.safety_stop_requested = False

    def observe(self) -> Observation:
        compressed = self.compressor.compress(self._raw_observation())
        self.compression_stats.append(compressed.stats)
        return compressed.observation

    def click(self, target: TargetMatch) -> bool:
        self.calls.append(FakeActionCall(name="click", node_id=target.node_id))
        node_id = target.node_id or ""
        page = self.state.page
        if page is MockPage.HOME and node_id == "home.search":
            self.state.page = MockPage.SEARCH
        elif page is MockPage.SEARCH and node_id == "search.submit":
            self.state.page = MockPage.RESULTS
        elif page is MockPage.RESULTS and node_id.startswith("result.cola.1"):
            self.state.selected_product = "可口可乐 500ml 2瓶"
            self.state.page = MockPage.DETAIL
        elif page is MockPage.RESULTS and node_id == "results.load_more":
            self.state.loaded_results = min(30, self.state.loaded_results + 10)
        elif page is MockPage.DETAIL and node_id == "detail.spec_selector":
            self.state.page = MockPage.SPEC_DIALOG
        elif page is MockPage.SPEC_DIALOG and node_id == "spec.2bottles":
            self.state.selected_spec = "2瓶"
            self.state.page = MockPage.DETAIL
        elif page is MockPage.DETAIL and node_id == "detail.coupon":
            self.state.page = MockPage.COUPONS
        elif page is MockPage.COUPONS and node_id == "coupon.claim":
            self.state.coupon_claimed = True
        elif page is MockPage.DETAIL and node_id == "detail.add_to_cart":
            self.state.cart_quantity = 2
            self.state.page = MockPage.CART
        elif page is MockPage.CART and node_id == "cart.checkout":
            self.state.page = MockPage.ORDER_CONFIRM
        elif page is MockPage.ORDER_CONFIRM and node_id == "order.submit":
            self.state.page = MockPage.PAYMENT
        else:
            return False
        self.state.revision += 1
        return True

    def set_text(self, target: TargetMatch, value: str) -> bool:
        self.calls.append(FakeActionCall(name="set_text", node_id=target.node_id, value=value))
        if self.state.page is not MockPage.SEARCH or target.node_id != "search.input":
            return False
        self.state.query = value
        self.state.revision += 1
        return True

    def scroll(self, target: TargetMatch | None, forward: bool) -> bool:
        self.calls.append(
            FakeActionCall(
                name="scroll_forward" if forward else "scroll_backward",
                node_id=target.node_id if target else None,
            )
        )
        if self.state.page is not MockPage.RESULTS:
            return False
        if forward:
            self.state.loaded_results = min(30, self.state.loaded_results + 10)
        else:
            self.state.loaded_results = max(10, self.state.loaded_results - 10)
        self.state.revision += 1
        return True

    def back(self) -> bool:
        self.calls.append(FakeActionCall(name="back"))
        previous = {
            MockPage.SEARCH: MockPage.HOME,
            MockPage.RESULTS: MockPage.SEARCH,
            MockPage.DETAIL: MockPage.RESULTS,
            MockPage.SPEC_DIALOG: MockPage.DETAIL,
            MockPage.COUPONS: MockPage.DETAIL,
            MockPage.CART: MockPage.DETAIL,
            MockPage.ORDER_CONFIRM: MockPage.CART,
            MockPage.PAYMENT: MockPage.ORDER_CONFIRM,
        }.get(self.state.page)
        if previous is None:
            return False
        self.state.page = previous
        self.state.revision += 1
        return True

    def wait(self, timeout_ms: int) -> bool:
        self.calls.append(FakeActionCall(name="wait", value=str(timeout_ms)))
        self.state.revision += 1
        return True

    def stop(self) -> bool:
        self.calls.append(FakeActionCall(name="stop"))
        self.safety_stop_requested = True
        return True

    def _raw_observation(self) -> Observation:
        nodes: list[ObservationNode] = [
            ObservationNode(
                node_id="root",
                class_name="android.widget.FrameLayout",
                children=["header", "content"],
            ),
            ObservationNode(node_id="header", text=self._title(), parent_id="root"),
            ObservationNode(
                node_id="content",
                class_name="android.widget.LinearLayout",
                parent_id="root",
                children=self._content_ids(),
            ),
        ]
        nodes.extend(self._content_nodes())
        return Observation(
            observation_id=f"mock-{self.state.page.value}-{self.state.revision}",
            platform="mock-shopping",
            package_name="com.pricesight.mockshopping",
            page_type=self._page_type(),
            nodes=nodes,
        )

    def _content_ids(self) -> list[str]:
        return [node.node_id for node in self._content_nodes()]

    def _content_nodes(self) -> list[ObservationNode]:
        page = self.state.page
        if page is MockPage.HOME:
            return [
                ObservationNode(
                    node_id="home.search",
                    text="搜索商品",
                    content_description="search",
                    clickable=True,
                    parent_id="content",
                ),
                ObservationNode(
                    node_id="home.empty_action",
                    content_description="empty_action",
                    clickable=True,
                    parent_id="content",
                ),
            ]
        if page is MockPage.SEARCH:
            return [
                ObservationNode(
                    node_id="search.input",
                    content_description="search_input",
                    editable=True,
                    parent_id="content",
                ),
                ObservationNode(
                    node_id="search.submit",
                    text="搜索",
                    content_description="search_submit",
                    clickable=True,
                    parent_id="content",
                ),
            ]
        if page is MockPage.RESULTS:
            nodes = [
                ObservationNode(
                    node_id="result.cola.1",
                    resource_id="result.cola.1",
                    text="可口可乐 500ml 2瓶 | Mock店A",
                    content_description="product_result",
                    clickable=True,
                    parent_id="content",
                ),
                ObservationNode(
                    node_id="result.cola.2",
                    resource_id="result.cola.2",
                    text="可口可乐 500ml 2瓶 | Mock店B",
                    content_description="product_result_duplicate",
                    clickable=True,
                    parent_id="content",
                ),
                ObservationNode(
                    node_id="result.cola.330",
                    text="可口可乐 330ml 6罐",
                    clickable=True,
                    parent_id="content",
                ),
            ]
            for index in range(4, self.state.loaded_results + 1):
                nodes.append(
                    ObservationNode(
                        node_id=f"result.long.{index}",
                        text=f"长列表测试商品 {index} 500ml",
                        clickable=True,
                        parent_id="content",
                    )
                )
            if self.state.loaded_results < 30:
                nodes.append(
                    ObservationNode(
                        node_id="results.load_more",
                        text="加载更多",
                        content_description="load_more",
                        clickable=True,
                        parent_id="content",
                    )
                )
            return nodes
        if page is MockPage.DETAIL:
            return [
                ObservationNode(node_id="detail.title", text="可口可乐 500ml 2瓶", parent_id="content"),
                ObservationNode(
                    node_id="detail.spec_selector",
                    text=self.state.selected_spec or "选择规格",
                    content_description="spec_selector",
                    clickable=True,
                    parent_id="content",
                ),
                ObservationNode(
                    node_id="detail.coupon",
                    text="优惠券",
                    content_description="coupon",
                    clickable=True,
                    parent_id="content",
                ),
                ObservationNode(
                    node_id="detail.add_to_cart",
                    text="加入购物车",
                    content_description="add_to_cart",
                    clickable=True,
                    parent_id="content",
                ),
                ObservationNode(node_id="detail.price", text="¥12.90", parent_id="content"),
            ]
        if page is MockPage.SPEC_DIALOG:
            return [
                ObservationNode(node_id="spec.dialog", text="规格选择", parent_id="content", children=["spec.capacity", "spec.count"]),
                ObservationNode(node_id="spec.capacity", text="容量 500ml", clickable=True, parent_id="spec.dialog"),
                ObservationNode(node_id="spec.count", text="数量", parent_id="spec.dialog", children=["spec.2bottles"]),
                ObservationNode(node_id="spec.2bottles", text="2瓶", content_description="spec_2_bottles", clickable=True, parent_id="spec.count"),
            ]
        if page is MockPage.COUPONS:
            return [
                ObservationNode(node_id="coupon.available", text="满10减2优惠券", parent_id="content"),
                ObservationNode(node_id="coupon.claim", text="领取优惠券", content_description="coupon_claim", clickable=True, parent_id="content"),
            ]
        if page is MockPage.CART:
            final = "¥10.90" if self.state.coupon_claimed else "¥12.90"
            return [
                ObservationNode(node_id="cart.title", text="购物车", parent_id="content"),
                ObservationNode(node_id="cart.item", text="可口可乐 500ml 2瓶 x2", parent_id="content"),
                ObservationNode(node_id="cart.final_price", text=f"最终价 {final}", parent_id="content"),
                ObservationNode(node_id="cart.checkout", text="去结算", content_description="checkout", clickable=True, parent_id="content"),
            ]
        if page is MockPage.ORDER_CONFIRM:
            return [
                ObservationNode(node_id="order.title", text="订单确认", parent_id="content"),
                ObservationNode(node_id="order.submit", text="提交订单", content_description="submit_order", clickable=True, parent_id="content"),
            ]
        return [
            ObservationNode(node_id="payment.title", text="模拟支付", parent_id="content"),
            ObservationNode(node_id="payment.password", text="请输入支付密码", parent_id="content"),
        ]

    def _title(self) -> str:
        return {
            MockPage.HOME: "Mock Shopping 首页",
            MockPage.SEARCH: "搜索页",
            MockPage.RESULTS: f"商品列表 {self.state.query}".strip(),
            MockPage.DETAIL: "商品详情",
            MockPage.SPEC_DIALOG: "规格弹窗",
            MockPage.COUPONS: "优惠券",
            MockPage.CART: "购物车",
            MockPage.ORDER_CONFIRM: "订单确认",
            MockPage.PAYMENT: "模拟支付",
        }[self.state.page]

    def _page_type(self) -> PageType:
        if self.state.page is MockPage.SEARCH:
            return PageType.SEARCH
        if self.state.page in {MockPage.DETAIL, MockPage.SPEC_DIALOG, MockPage.COUPONS}:
            return PageType.PRODUCT
        if self.state.page is MockPage.CART:
            return PageType.CART
        return PageType.UNKNOWN
