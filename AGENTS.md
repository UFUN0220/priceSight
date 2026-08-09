# AGENTS.md

# Mobile Price Agent

## 1. Project Goal

This repository implements a mobile Computer-Use Agent for cross-platform product comparison.

The system observes Android application interfaces through Android Accessibility APIs, converts raw accessibility trees into compact structured observations, makes decisions through deterministic workflows and LLM-based agents, executes actions on Android, and evaluates execution quality.

The target demonstration scenario is cross-platform product comparison across shopping / instant-retail applications.

Typical task:

```text
User request
    ↓
Search product on multiple platforms
    ↓
Identify matching product and specification
    ↓
Read price / coupon / promotion information
    ↓
Optionally add product to cart
    ↓
Calculate comparable final price
    ↓
Return comparison and recommendation
```

This is primarily a Computer-Use Agent engineering project, not an e-commerce backend.

The important engineering topics are:

- Android GUI observation
- Accessibility tree compression
- structured agent context
- deterministic Workflow + Agent hybrid execution
- structured LLM output
- product/specification semantic parsing
- action grounding
- fallback and recovery
- event-driven execution
- cross-platform abstraction
- evaluation and Bad Case iteration

---

# 2. Safety Boundary

The project MUST run in SAFE MODE by default.

The agent may:

- open supported applications
- search
- navigate pages
- inspect visible product information
- inspect price and promotion information
- select specifications
- claim coupons only when explicitly enabled
- add items to cart only when explicitly enabled
- return comparison results

The agent MUST NOT:

- submit a real order
- perform payment
- enter payment passwords
- bypass CAPTCHA
- bypass platform security controls
- bypass account restrictions
- automate account registration
- automatically confirm purchases
- access private data unrelated to the current task

Any detected page representing:

```text
submit order
payment
password
CAPTCHA
identity verification
```

must trigger a safety stop.

Represent this as:

```python
SafetyDecision.STOP
```

The action executor must reject payment-related actions even if an LLM requests them.

Safety rules belong in deterministic code, never only in prompts.

---

# 3. Development Strategy

Do NOT attempt to implement the entire system in one change.

Development must proceed incrementally.

Each phase must:

1. inspect existing code before making changes;
2. preserve previously working functionality;
3. implement only the current coherent milestone;
4. add or update tests;
5. run relevant tests and builds;
6. update `docs/PHASE_STATUS.md`;
7. report what was implemented, tested, and still missing.

Do not rewrite working modules without a clear reason.

Prefer small reviewable changes over large rewrites.

Do not prematurely implement future phases.

---

# 4. Repository Architecture

Target repository structure:

```text
mobile-price-agent/
│
├── AGENTS.md
├── README.md
├── .env.example
├── .gitignore
├── pyproject.toml
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   │
│   │   ├── api/
│   │   │
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── logging.py
│   │   │   └── safety.py
│   │   │
│   │   ├── observation/
│   │   │   ├── models.py
│   │   │   ├── parser.py
│   │   │   ├── compressor.py
│   │   │   └── serializer.py
│   │   │
│   │   ├── action/
│   │   │   ├── models.py
│   │   │   ├── matcher.py
│   │   │   ├── executor.py
│   │   │   └── verifier.py
│   │   │
│   │   ├── workflow/
│   │   │   ├── models.py
│   │   │   ├── loader.py
│   │   │   └── engine.py
│   │   │
│   │   ├── agent/
│   │   │   ├── models.py
│   │   │   ├── planner.py
│   │   │   ├── router.py
│   │   │   └── prompts/
│   │   │
│   │   ├── llm/
│   │   │   ├── base.py
│   │   │   ├── openai_compatible.py
│   │   │   ├── anthropic_compatible.py
│   │   │   └── fake.py
│   │   │
│   │   ├── parser/
│   │   │   ├── product.py
│   │   │   ├── quantity.py
│   │   │   ├── specification.py
│   │   │   └── price.py
│   │   │
│   │   ├── platform/
│   │   │   ├── base.py
│   │   │   ├── mock/
│   │   │   ├── meituan/
│   │   │   ├── jd/
│   │   │   └── taobao/
│   │   │
│   │   ├── comparison/
│   │   │
│   │   ├── cache/
│   │   │
│   │   └── transport/
│   │
│   └── tests/
│
├── android-client/
│   ├── app/
│   └── gradlew / gradlew.bat
│
├── mock-shopping-app/
│
├── workflows/
│   ├── search_product.yaml
│   ├── inspect_product.yaml
│   └── add_to_cart.yaml
│
├── evaluation/
│   ├── datasets/
│   ├── metrics/
│   ├── runners/
│   └── reports/
│
├── scripts/
│
└── docs/
    ├── ARCHITECTURE.md
    ├── PHASE_STATUS.md
    ├── SAFETY.md
    └── DEVELOPMENT.md
```

The exact structure may evolve, but responsibilities must remain separated.

---

# 5. Backend Technology

Use:

```text
Python 3.12+
FastAPI
Pydantic v2
pytest
httpx
PyYAML
```

Prefer `uv` for Python environment and dependency management.

Use asynchronous code only where it provides actual value such as:

- HTTP calls
- model calls
- WebSocket communication
- concurrent platform tasks

Do not convert purely computational code to async.

Use type annotations for all public functions.

Prefer explicit Pydantic models over untyped dictionaries.

Avoid `Any` unless technically unavoidable.

---

# 6. Android Technology

Use Kotlin for the Android client.

The Android component is responsible only for device-level capabilities:

```text
Accessibility event collection
Accessibility tree extraction
action execution
gesture execution
event transport
debug information
```

Business reasoning must remain in the Python backend.

Do not place product comparison or LLM logic in Android code.

The Android client must expose accessibility nodes using stable serialized data rather than leaking Android framework objects outside the client.

Every observed node should support fields where available such as:

```text
node_id
class_name
text
content_description
resource_id
clickable
scrollable
editable
enabled
visible
bounds
depth
parent_id
children
```

Do not assume `resource_id`, `text`, or `content_description` always exists.

---

# 7. Observation Model

Raw Accessibility trees must never be sent directly to the LLM without processing.

Observation processing pipeline:

```text
Raw Accessibility Tree
        ↓
Normalization
        ↓
Invisible node pruning
        ↓
Empty node pruning
        ↓
Redundant structural node pruning
        ↓
Duplicate semantic node merging
        ↓
Interactive-node prioritization
        ↓
Compact structured observation
```

Compression must preserve information required for actions.

Never remove a node only because its text is empty if it:

- is clickable;
- is editable;
- is scrollable;
- contains meaningful descendants;
- provides useful bounds;
- acts as an action target.

Every compression run should be measurable.

Record:

```text
raw_node_count
compressed_node_count
compression_ratio
serialized_character_count
estimated_token_count if available
processing_latency_ms
```

---

# 8. Agent Context

Do not give the model the entire interaction history blindly.

The context should contain only relevant information:

```text
user goal
current platform
current workflow state
current page type
compact current observation
important previous action
important previous result
known product constraints
safety state
remaining retry budget
```

Historical UI trees must not accumulate without bounds.

Maintain explicit limits for:

- observation size
- action history
- retries
- LLM calls
- workflow steps

---

# 9. Workflow + Agent Hybrid

Do not use an LLM for deterministic operations unnecessarily.

Stable operations should be implemented as YAML-driven workflows where practical.

Examples:

```text
open search
enter keyword
submit search
open known product result
navigate back
read cart
```

Use the Agent for ambiguous decisions such as:

```text
which result best matches the requested product
which specification corresponds to the requested quantity
whether two differently named products are equivalent
how to recover from unexpected UI state
whether the current page satisfies the task goal
```

Target architecture:

```text
User Goal
   ↓
Task Router
   ├── Workflow Engine
   └── Agent Planner
            ↓
       Action Grounding
            ↓
       Android Executor
            ↓
        Verification
            ↓
       Next Observation
```

---

# 10. LLM Layer

Business code must not depend directly on one model vendor.

Define a provider abstraction.

At minimum support:

```text
OpenAI-compatible provider
Anthropic-compatible provider
Fake provider for tests
```

Configuration must come from environment variables.

Never hard-code:

- API keys
- base URLs
- model secrets
- account information

All model decisions that trigger program behavior must use structured schemas validated through Pydantic.

Example conceptual schema:

```python
class AgentDecision(BaseModel):
    thought_summary: str
    action: Action
    target: Target | None
    confidence: float
    requires_verification: bool
```

Do not parse important actions from free-form prose.

The application must remain testable without an external LLM by using `FakeLLMProvider`.

---

# 11. Product Parsing

Prefer deterministic parsing before model inference.

Pipeline:

```text
raw product text
    ↓
normalization
    ↓
regex / quantity parser
    ↓
unit normalization
    ↓
specification parser
    ↓
confidence evaluation
    ↓
LLM fallback only when ambiguous
```

Normalize common units including:

```text
ml
L
g
kg
piece
pack
bottle
can
cup
box
```

Preserve both normalized fields and original text.

Do not assume every promotional string describes the purchased quantity.

Handle cases such as:

```text
550ml×12
330ml*6
1L×2 + 250ml×2 gift
2 cups
buy 2 get 1
combo products
nested specifications
```

---

# 12. Action Harness

LLM output does not directly execute arbitrary coordinates.

Actions must pass through an action grounding layer.

Preferred target resolution order:

```text
1. stable resource identifier
2. exact accessible node match
3. text/content-description match
4. normalized semantic match
5. fuzzy candidate match
6. fresh bounding-box coordinate fallback
```

Never use stale coordinates after the page has changed.

After important actions, obtain a fresh observation and verify that the expected state transition occurred.

Action results should distinguish:

```text
SUCCESS
TARGET_NOT_FOUND
ACTION_REJECTED
STATE_UNCHANGED
TIMEOUT
SAFETY_BLOCKED
RETRY_EXHAUSTED
```

Retries must be bounded.

Repeated actions on the same state must trigger re-observation or replanning instead of infinite loops.

---

# 13. Partial Observability

Treat mobile GUI execution as a partially observable environment.

Do not assume one event means a page is fully loaded.

Page interpretation may consider multiple recent accessibility events when necessary.

Use explicit state machines for genuinely multi-step UI structures such as nested specification dialogs.

Do not introduce complicated state machines before real Bad Cases justify them.

---

# 14. Platform Abstraction

Platform-specific UI selectors must not leak into generic agent logic.

Define a platform adapter interface.

Conceptual responsibilities:

```text
identify_platform()
identify_page()
extract_products()
extract_price()
extract_promotions()
extract_selected_spec()
build_platform_hints()
```

Platform implementations belong under:

```text
platform/meituan/
platform/jd/
platform/taobao/
```

Generic modules must not contain hard-coded platform-specific text unless required for detection.

External application interfaces may change, so adapters must fail gracefully.

---

# 15. Transport

Start with the simplest reliable local transport.

The architecture must allow both:

```text
polling transport
event-driven transport
```

Later phases should preserve polling as a measurable baseline while introducing event-driven communication.

Do not remove the baseline before performance comparison data has been collected.

For USB-connected Android development, local development may use ADB port forwarding/reverse where appropriate.

---

# 16. Cache

Caching exists to reduce repeated GUI navigation or repeated model interpretation, not to hide correctness problems.

Cache keys must include sufficient identity information such as:

```text
platform
store
normalized product
normalized specification
```

Cache entries should record timestamps and support expiration.

A stale cache result must never automatically trigger a purchase-related action.

---

# 17. Evaluation

This project must contain measurable evaluation rather than anecdotal claims.

Track at minimum:

```text
Accessibility tree compression ratio
product parsing exact-match accuracy
action success rate
task success rate
average steps per task
average LLM calls per task
average retries per task
end-to-end latency
cache hit rate
safety-stop correctness
```

Evaluation outputs must be reproducible.

Raw benchmark results should be saved under:

```text
evaluation/reports/
```

Never write resume performance numbers that were not produced by an actual benchmark.

Generated or synthetic evaluation samples must not be described as manually annotated until a human has actually reviewed them.

Bad Cases should be retained and categorized.

---

# 18. Testing

Backend:

```powershell
uv run pytest
```

Run formatting/lint/type checks if configured.

Android:

```powershell
.\android-client\gradlew.bat test
.\android-client\gradlew.bat assembleDebug
```

Mock application:

```powershell
.\mock-shopping-app\gradlew.bat test
.\mock-shopping-app\gradlew.bat assembleDebug
```

Use unit tests for deterministic logic.

Use integration tests for:

```text
workflow transitions
observation compression
action matching
provider structured outputs
platform adapter behavior
```

Use fixture accessibility trees so most backend tests do not require a physical Android device.

---

# 19. Secrets and Local Files

Never commit:

```text
.env
API keys
Android signing secrets
user account credentials
captured personal information
private cookies
payment information
```

Provide `.env.example`.

Sanitize captured UI fixtures before committing them.

---

# 20. Logging

Logs must be structured and useful for replay.

For each agent step, record where possible:

```text
task_id
step_id
platform
page_type
observation_hash
action
target
match_strategy
confidence
execution_result
latency
retry_count
```

Never log secrets.

LLM prompts and responses used for debugging must be sanitized before persistence.

---

# 21. Error Handling

Do not silently catch broad exceptions.

Catch expected exceptions near the layer that can handle them.

Convert infrastructure failures into explicit domain errors.

Examples:

```text
DeviceDisconnectedError
ObservationUnavailableError
TargetNotFoundError
WorkflowStateError
ProviderError
SafetyViolationError
```

User-facing API errors must not expose secrets or internal stack traces.

---

# 22. Documentation

Keep the following current:

```text
README.md
docs/ARCHITECTURE.md
docs/PHASE_STATUS.md
docs/SAFETY.md
```

`docs/PHASE_STATUS.md` should indicate:

```text
completed phases
current capabilities
tests executed
known limitations
next milestone
```

Do not claim unfinished functionality.

---

# 23. Codex Working Rules

Before editing:

1. read this `AGENTS.md`;
2. inspect the existing repository;
3. inspect `docs/PHASE_STATUS.md` if present;
4. identify the smallest coherent implementation for the requested phase.

During implementation:

- preserve established architecture;
- prefer existing utilities over duplicates;
- keep domain logic testable;
- avoid unnecessary dependencies;
- do not add frameworks merely for resume keywords;
- do not fabricate benchmark results;
- do not change unrelated files;
- do not perform destructive Git operations;
- do not make real purchases;
- do not run real payment flows.

After implementation:

1. run relevant automated tests;
2. run builds when applicable;
3. fix failures caused by the current change;
4. update `docs/PHASE_STATUS.md`;
5. summarize implementation and verification.

If a required system dependency is unavailable, report the exact missing dependency and the command/check used to determine that. Do not fake successful execution.

---

# 24. Definition of Done

A phase is complete only when:

```text
implementation exists
        +
automated tests exist where practical
        +
tests/build pass
        +
documentation is updated
        +
no fabricated metrics
        +
previous functionality remains working
```

A feature that only exists in README text is not implemented.

A feature that has never been measured must not have a performance number attached to it.

The final project should prioritize engineering depth and explainability over feature count.