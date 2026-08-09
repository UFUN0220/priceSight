"""Configurable fixture adapter; not a real Meituan, JD, or Taobao integration."""

from app.platform.mock.adapter import MockShoppingAdapter


class FixtureOfferAdapter(MockShoppingAdapter):
    """Reuse the controlled mock node contract for isolated source fixtures."""

    def __init__(self, platform_id: str, package_name: str) -> None:
        super().__init__()
        self.platform_id = platform_id
        self.package_name = package_name
