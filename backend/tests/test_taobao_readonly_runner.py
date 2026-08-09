"""Safety and report-contract tests for the live Taobao read-only runner."""

from scripts.run_taobao_readonly import _base_report, run


def test_readonly_runner_rejects_hosts_outside_taobao_allowlist() -> None:
    report = run("https://evil.example/search?q=iphone17", headed=False)

    assert report["status"] == "BLOCKED"
    assert report["host_verified"] is False
    assert report["real_page_accessed"] is False
    assert report["external_side_effect"] is False


def test_readonly_report_contract_is_explicitly_non_mutating() -> None:
    report = _base_report("https://uland.taobao.com/sem/tbsearch?q=iphone17")

    assert report["query"] == "iphone17"
    assert report["host_verified"] is True
    assert report["external_side_effect"] is False
    assert report["fixture_regression_result"] == "run_separately"
    assert report["backend_test_result"] == "run_separately"
