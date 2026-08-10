# PriceSight Agent Decision Boundary

PriceSight follows a fail-closed `Rule → Workflow → LLM → Runtime` boundary. The boundary is a correctness contract, not a description of which component is most sophisticated.

## Deterministic responsibilities

`Rule` owns operations whose result should be reproducible from current evidence:

- normalize Unicode, separators and units;
- parse quantity candidates and separate the primary package from gift components;
- classify price candidates as displayed, after-sale, original, member or starting;
- rank candidates without choosing the lowest number;
- calculate Decimal effective prices from confirmed `PricingRule` objects;
- mark `UNRESOLVED` or `NEED_MORE_EVIDENCE` when a threshold, membership identity, range or conflicting candidate cannot be verified;
- validate Pydantic action/LLM schemas;
- reject stale observations and payment/order/security actions through `StaleObservationGuard` and `SafetyGuard`.

Rules do not infer a discount merely because a promotion-shaped word exists. A rule needs an amount and a confirmed condition, with source evidence preserved.

## Workflow responsibilities

`Workflow` owns stable, low-ambiguity transitions such as opening search, entering a query, submitting search, returning, and reading a known page state. It bounds steps and retries. A workflow must hand off when the page is semantically ambiguous or the expected state transition is not observed.

## LLM responsibilities

`LLM` owns bounded semantic work:

- understand the user's product goal;
- select among candidate products when deterministic identity matching is insufficient;
- interpret complex title/SKU language or a promotion description into a validated `LLMParseSuggestion`/`DiscountRule`;
- choose the next action or recovery step when the workflow cannot identify a stable transition.

LLM output is never a price calculation or a direct coordinate command. It is schema-validated, tied to the current observation, and rejected on malformed output, low confidence or unsafe content.

## Runtime responsibilities

`Runtime` only observes and executes device/browser capabilities. It supplies fresh Accessibility/DOM observations, node identity and action results. It must not decide product equivalence, invent price evidence or bypass SafetyGuard. Real App, fixture, Mock App and public read-only web evidence retain separate labels.

## Fallback sequence

```text
fresh Observation
  → deterministic extraction and evidence ranking
  → Workflow for stable transition
  → structured LLM only for unresolved semantics
  → schema validation + confidence/abstention
  → ActionGrounder bound to observation_id
  → Runtime action
  → fresh observation and verification
```

If the chain cannot establish product/specification/price evidence, the output is `UNKNOWN`, `UNRESOLVED` or `NEED_MORE_EVIDENCE`; the system does not force a comparison. Payment, order confirmation, CAPTCHA and identity verification remain deterministic safety stops.

## Current boundary limitations

- The evaluation FakeLLM is a deterministic replay provider and does not establish online model accuracy.
- JD/Meituan adapters and Android flows are fixture/Mock contracts; they are not evidence of live App success.
- Threshold discounts can be calculated only when the evaluated subtotal is known; otherwise the PricingEngine returns `UNRESOLVED`.
