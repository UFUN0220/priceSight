# PriceSight Evaluation Baseline

> Frozen at commit `034b94a3b630a9d342903ac45c46982bd714f6fd` on `2026-08-10T16:16:48.180701+00:00`. This file is write-once.
> The HUMAN source is reconstructed anonymized offline replay; it is not live-platform accuracy.

## Tests

- Command: `F:\projects_2027\PriceSight\.venv\Scripts\python.exe -m pytest -q --cov=backend/app --cov-branch --cov-report=term-missing`
- Return code: `0`
- Passed: `161`
- Branch coverage: `None%`

## Evaluation

| Scope | CORE | STRICT | Quantity | Specification | Displayed price | Effective price |
| --- | --- | --- | --- | --- | --- | --- |
| DEV | 5/32 (15.62%) | 2/32 (6.25%) | 23/32 (71.88%) | 14/32 (43.75%) | 8/31 (25.81%) | 0/10 (0.00%) |
| HOLDOUT | 0/8 (0.00%) | 0/8 (0.00%) | 3/8 (37.50%) | 3/8 (37.50%) | 2/6 (33.33%) | 0/2 (0.00%) |
| ALL | 16/96 (16.67%) | 12/96 (12.50%) | 69/92 (75.00%) | 47/96 (48.96%) | 18/85 (21.18%) | 1/24 (4.17%) |

## HUMAN_VERIFIED_ONLY

- CORE: 5/40 (12.50%)
- STRICT: 2/40 (5.00%)
- Quantity: 26/40 (65.00%)
- Specification: 17/40 (42.50%)
- Displayed price: 10/37 (27.03%)
- Effective price: 0/12 (0.00%)

## Bad Case counts

| Type | Samples | Human | Hybrid errors | Human hybrid errors |
| --- | ---: | ---: | ---: | ---: |
| `bulk` | 15 | 5 | 15 | 5 |
| `coupon_price` | 9 | 5 | 9 | 5 |
| `duplicate_node` | 3 | 3 | 3 | 3 |
| `dynamic_price` | 6 | 3 | 4 | 1 |
| `gift` | 9 | 3 | 8 | 3 |
| `missing_information` | 2 | 0 | 2 | 0 |
| `multi_pack` | 4 | 0 | 0 | 0 |
| `multi_spec` | 1 | 0 | 0 | 0 |
| `popup_loading` | 3 | 3 | 3 | 3 |
| `price_range` | 6 | 2 | 6 | 2 |
| `quantity_ambiguity` | 8 | 2 | 7 | 2 |
| `second_item_discount` | 6 | 3 | 6 | 3 |
| `sku_mixed_text` | 10 | 5 | 10 | 5 |
| `title_noise` | 6 | 4 | 4 | 4 |
| `unit_ambiguity` | 8 | 2 | 7 | 2 |

## Reproduction

```powershell
uv run python scripts/build_evaluation_baseline.py
```
