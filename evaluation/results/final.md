# PriceSight Targeted Improvement Evaluation

> Final replay generated at `2026-08-10T17:06:53.974034+00:00`; baseline remains frozen at `034b94a3b630a9d342903ac45c46982bd714f6fd`.
> No annotation, DEV/HOLDOUT membership or metric definition was changed.

## Baseline → final

| Scope | CORE | STRICT | Quantity | Specification | Displayed price | Effective price |
| --- | --- | --- | --- | --- | --- | --- |
| DEV | 5/32 (15.62%) → 5/32 (15.62%) | 2/32 (6.25%) → 2/32 (6.25%) | 23/32 (71.88%) → 23/32 (71.88%) | 14/32 (43.75%) → 14/32 (43.75%) | 8/31 (25.81%) → 8/31 (25.81%) | 0/10 (0.00%) → 0/10 (0.00%) |
| HOLDOUT | 0/8 (0.00%) → 0/8 (0.00%) | 0/8 (0.00%) → 0/8 (0.00%) | 3/8 (37.50%) → 3/8 (37.50%) | 3/8 (37.50%) → 3/8 (37.50%) | 2/6 (33.33%) → 2/6 (33.33%) | 0/2 (0.00%) → 0/2 (0.00%) |
| ALL | 16/96 (16.67%) → 16/96 (16.67%) | 12/96 (12.50%) → 12/96 (12.50%) | 69/92 (75.00%) → 69/92 (75.00%) | 47/96 (48.96%) → 49/96 (51.04%) | 18/85 (21.18%) → 18/85 (21.18%) | 1/24 (4.17%) → 1/24 (4.17%) |

## HUMAN_VERIFIED_ONLY

- CORE: 5/40 (12.50%)
- STRICT: 2/40 (5.00%)
- Quantity: 26/40 (65.00%)
- Specification: 17/40 (42.50%)
- Displayed price: 10/37 (27.03%)
- Effective price: 0/12 (0.00%)

## Bad Case delta

| Type | Baseline errors | Final errors | Delta |
| --- | ---: | ---: | ---: |
| `bulk` | 15 | 15 | +0 |
| `coupon_price` | 9 | 9 | +0 |
| `duplicate_node` | 3 | 3 | +0 |
| `dynamic_price` | 4 | 4 | +0 |
| `gift` | 8 | 8 | +0 |
| `missing_information` | 2 | 2 | +0 |
| `multi_pack` | 0 | 0 | +0 |
| `multi_spec` | 0 | 0 | +0 |
| `popup_loading` | 3 | 3 | +0 |
| `price_range` | 6 | 6 | +0 |
| `quantity_ambiguity` | 7 | 7 | +0 |
| `second_item_discount` | 6 | 6 | +0 |
| `sku_mixed_text` | 10 | 10 | +0 |
| `title_noise` | 4 | 4 | +0 |
| `unit_ambiguity` | 7 | 7 | +0 |

## Abstention evidence

- DEV: ambiguous=0, missing displayed=24, missing effective=30
- HOLDOUT: ambiguous=1, missing displayed=6, missing effective=8
- ALL: ambiguous=4, missing displayed=78, missing effective=89

## Boundary

HUMAN rows are reconstructed anonymized offline replay. HOLDOUT remains frozen and is reported even when it is low. FakeLLM, Mock Android, Browser Mock and fixture adapters are controlled evidence, not real-platform accuracy.
