"""Tests for browser DOM normalization without requiring a browser binary."""

from app.runtime.browser import BrowserObservationParser


def test_browser_snapshot_maps_dom_semantics_to_observation() -> None:
    observation = BrowserObservationParser("mock-web").parse(
        {
            "url": "http://127.0.0.1:8000/search",
            "title": "Mock Web 搜索结果",
            "nodes": [
                {
                    "node_id": "browser.node.0",
                    "class_name": "button",
                    "text": "可口可乐 500ml 2瓶",
                    "content_description": "product_result",
                    "resource_id": "product-result-1",
                    "clickable": True,
                    "enabled": True,
                    "visible": True,
                    "bounds": [0, 0, 300, 80],
                    "depth": 0,
                    "children": [],
                }
            ],
        },
        "obs-1",
    )

    assert observation.platform == "mock-web"
    assert observation.page_type.value == "search"
    assert observation.source_url == "http://127.0.0.1:8000/search"
    assert observation.nodes[0].resource_id == "product-result-1"


def test_browser_parser_classifies_order_confirmation_as_cart_safety_boundary() -> None:
    observation = BrowserObservationParser("mock-web").parse(
        {
            "url": "http://127.0.0.1:8000/checkout",
            "title": "订单确认",
            "nodes": [
                {
                    "node_id": "browser.node.0",
                    "text": "提交订单",
                    "content_description": "submit_order",
                    "clickable": True,
                    "enabled": True,
                    "visible": True,
                    "bounds": [0, 0, 100, 40],
                    "depth": 0,
                    "children": [],
                }
            ],
        },
        "obs-2",
    )

    assert observation.page_type.value == "cart"
    assert "订单确认" in (observation.title or "")
