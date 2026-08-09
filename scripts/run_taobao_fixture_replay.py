"""Run the Taobao structured page fixture through the browser observation path."""

import json
from pathlib import Path

from app.platform.taobao import TaobaoPlatformAdapter, TaobaoStructuredPageFixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "evaluation" / "fixtures" / "web" / "taobao_iphone17_page_structure.json"
REPORT = ROOT / "evaluation" / "reports" / "phase16_taobao_fixture_replay.json"


def main() -> None:
    fixture = TaobaoStructuredPageFixture.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    adapter = TaobaoPlatformAdapter()
    observation = adapter.observation_from_structured_page_fixture(fixture)
    extraction = adapter.extract_products(observation)
    selected_tabs = [
        tab.label
        for tab in fixture.page_structure.search_bar.search_tabs
        if tab.selected
    ]
    report = {
        "mode": "taobao_sanitized_fixture_replay",
        "real_page_accessed": False,
        "external_side_effect": False,
        "source_fixture": str(FIXTURE.relative_to(ROOT)),
        "search_query": fixture.page_structure.search_bar.search_query,
        "selected_tabs": selected_tabs,
        "page": (
            fixture.page_structure.product_list.pagination.current_page
            if fixture.page_structure.product_list.pagination
            else None
        ),
        "has_next": (
            fixture.page_structure.product_list.pagination.has_next
            if fixture.page_structure.product_list.pagination
            else False
        ),
        "recognized": extraction.recognized,
        "product_count": len(extraction.products),
        "prices": [str(product.price.amount) for product in extraction.products if product.price],
        "selector_roles": sorted(extraction.selector_candidates),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
