# Resume Evidence Boundary

This document lists claims that can be defended from repository code, automated tests or explicitly labeled controlled execution. It does not convert Mock, fixture or reconstructed annotation results into live-platform claims.

## A. Can be written directly

- Built a Python/FastAPI/Pydantic Computer-Use Agent prototype with structured Observation DTOs for Android Accessibility and Browser DOM/ARIA inputs.
- Implemented deterministic Observation pruning/compression with measured node/serialized-size statistics and regression tests for actionable empty nodes and duplicate structure.
- Implemented rule-first quantity/specification parsing with Decimal normalization, structured LLM fallback and Pydantic validation.
- Implemented action grounding with current `observation_id` checks, stale-observation rejection, bounded retries and post-action verification.
- Implemented deterministic SAFE MODE/SafetyGuard stops for order confirmation, payment, password, CAPTCHA and identity-verification boundaries.
- Added a price evidence pipeline that preserves source text, node/selector identity, normalized amount, parser and confidence, with explicit abstention for price ranges, member prices, starting prices and conflicts.
- Added a deterministic Decimal PricingEngine for explicitly evidenced discounts/fees and a structured offline evaluation with DEV/HOLDOUT, provenance audit, CORE/STRICT contracts and Bad Case taxonomy.
- Maintained automated Python tests and CI quality gates; the repository’s prior verified run recorded 161 passed and 86% branch coverage before this reinforcement work.
- Verified Android Emulator/Mock Shopping and Browser Mock flows as controlled evidence, including safety blocking without real order submission.

## B. Can be expanded in an interview

- Why product quantity parsing must distinguish unit quantity, pack count, total quantity and gift quantity.
- Why price ranking must use semantic labels and evidence rather than DOM order or the minimum numeric value.
- Why effective price is a separate deterministic calculation and why threshold/member/shipping conditions can force `UNRESOLVED`.
- How Rule, Workflow, structured LLM and Runtime boundaries prevent an LLM from inventing prices or executing stale coordinates.
- How CORE and STRICT exact metrics differ, why HOLDOUT is frozen, and why reconstructed human annotations are not live accuracy.
- How Android service lifecycle interference led to the External Runtime Harness and why Mock App success is not a real shopping App claim.

## C. Currently prohibited claims

- “85%+ real-world product/price accuracy.”
- “High-accuracy effective/on-arrival price across platforms.”
- “JD, Meituan and Taobao real Android Apps are fully connected and verified.”
- “Automated real order placement, payment, coupon claiming or account login.”
- “HOLDOUT generalization is solved.” Current frozen HUMAN report records CORE `5/40`, STRICT `2/40`, and HOLDOUT `0/8` for both exact metrics; these numbers must not be hidden or re-labeled.
- “FakeLLM results are online LLM performance.”
