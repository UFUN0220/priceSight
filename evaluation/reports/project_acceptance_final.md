# PriceSight 项目最终验收报告

**验收日期：** 2026-08-09  
**基准：** 沿用 `evaluation/reports/project_acceptance_2026-08-09.json` 的八个维度和权重  
**范围：** 不新增业务功能，只复验阶段 0—7 的实现并整理 Demo/面试材料

## 1. 最终结论

本项目通过了离线后端、Python 工程质量、Browser Mock Chromium、淘宝脱敏 fixture、跨平台 fixture，以及一次受 allowlist 约束的淘宝公开页面只读 smoke。Android Client/Mock App 的本地 unit test 和 `assembleDebug` 通过，但 Android instrumented/runtime 因本机没有 emulator/AVD/system image 未验证；Android lint 因离线缺少 `lint-gradle:31.5.2` 阻断；远端 CI 没有运行记录。

**最终评分：84/100，weighted score 83.8，四舍五入为 84。** 该评分使用与 2026-08-09 报告相同的维度和权重；提升来自本轮已有质量门禁和淘宝公开只读证据，不是调整评分标准。项目仍不是生产就绪项目。

## 2. 证据分级

| 等级 | 含义 |
|---|---|
| `VERIFIED` | 本机命令或真实公开只读 smoke 已按本报告命令完成并通过 |
| `FIXTURE_VERIFIED` | 脱敏 fixture 回放通过；不等价于实时平台 |
| `MOCK_VERIFIED` | Mock App/Web 或 Fake Provider 通过；不等价于真实设备/模型 |
| `BUILD_ONLY` | 仅证明构建产物/编译通过，不证明运行时 |
| `NOT_VERIFIED` | 当前没有足够运行证据 |
| `BLOCKED` | 已执行检查，但环境/依赖阻断 |

## 3. 测试与构建结果

| 能力 | 命令/证据 | 状态 | 解释 |
|---|---|---|---|
| Backend 全量测试 | `uv run python scripts/run_quality_gate.py` | `VERIFIED` | 132 passed，0 failed，0 warnings |
| Python compile | quality gate 内 `compileall`；另行执行 compileall | `VERIFIED` | 通过 |
| Ruff | quality gate | `VERIFIED` | 通过 |
| mypy | quality gate | `VERIFIED` | 79 source files，0 issues |
| pre-commit | quality gate | `VERIFIED` | 通过 |
| coverage | quality gate | `VERIFIED` | branch coverage 85%，门槛 80% |
| Browser Mock E2E | `uv run python scripts/run_browser_mock.py` | `MOCK_VERIFIED` | 读取 `10.90`，订单确认返回 `SAFETY_BLOCKED`，未提交订单 |
| 淘宝 fixture replay | `uv run python scripts/run_taobao_fixture_replay.py` | `FIXTURE_VERIFIED` | 2 个商品，价格均为 `5999.00`，真实页面未访问 |
| 跨平台 fixture tests | 24 focused tests | `FIXTURE_VERIFIED` | Taobao/JD/Meituan/Mock adapter 和比较回归通过 |
| Evaluation v2 | `uv run python scripts/run_evaluation_v2.py` | `FIXTURE_VERIFIED` | 10 条样本、全部 UNREVIEWED，机器一致性指标可复现 |
| 淘宝 live readonly | `uv run python scripts/run_taobao_readonly.py --report ...` | `VERIFIED` | 公开页面真实访问；140 商品链接、45 展示价格、无副作用 |
| Android Client unit test | Gradle `test --offline` | `VERIFIED` | 本地通过 |
| Android Client APK | Gradle `assembleDebug --offline` | `BUILD_ONLY` | 构建通过，不代表设备运行 |
| Mock App unit test | Gradle `test --offline` | `VERIFIED` | 本地通过 |
| Mock App APK | Gradle `assembleDebug --offline` | `BUILD_ONLY` | 构建通过，不代表设备运行 |
| Android lint | Gradle `lintDebug --offline` | `BLOCKED` | 缺少缓存 `com.android.tools.lint:lint-gradle:31.5.2` |
| Android Runtime E2E | instrumented test | `NOT_VERIFIED/BLOCKED` | `adb` 可用，但 emulator executable 不存在、AVD 数量为 0、无 system image |
| 远端 CI | `.github/workflows/ci.yml` | `NOT_VERIFIED` | workflow 已配置，本次无 GitHub Actions run 证据 |
| diff whitespace | `git diff --check` | `VERIFIED` | 通过 |

Build Success 没有被写成 Runtime Verified：Android APK 明确标为 `BUILD_ONLY`。

## 4. 实时淘宝只读证据边界

本次 runner 使用 `https://uland.taobao.com/sem/tbsearch?q=iphone17`，host allowlist 校验通过，页面状态为 `SEARCH_RESULT`，生成了 BrowserRuntime Observation。抽取策略包含 `href_product_id` 和 text-assisted fallback；真实页面访问成功但只代表本次公开页面和当前 selector 证据。

runner 没有登录、输入、点击、加购、订单提交或支付；报告中的 `external_side_effect=false`。这项结果是 `VERIFIED` 的真实只读 smoke，不应与淘宝 fixture、Mock Web 或 JD/美团 fixture 合并统计。

## 5. Evaluation 可信度

当前数据集共 10 条：8 条 `synthetic`，2 条淘宝 `fixture`；`HUMAN_VERIFIED=0`。因此不发布人工真实准确率。

| 指标 | numerator | denominator | 解释 |
|---|---:|---:|---|
| Rule accuracy | 8 | 10 | 未人工复核样本上的 deterministic parser 一致性 |
| Rule quantity | 6 | 6 | 有 quantity 期望字段的样本 |
| Rule spec | 10 | 10 | 机器期望字段一致性 |
| Rule price | 2 | 2 | 有 price 期望字段的样本 |
| Rule ambiguous | 8 | 10 | 未人工复核的 ambiguity 回归 |
| LLM fallback accuracy | 4 | 4 | FakeLLM structured replay，不是线上模型 |
| Hybrid accuracy | 10 | 10 | rule-first + FakeLLM 回放 |
| LLM invocation rate | 4 | 10 | fallback 调用数/样本数 |
| Schema failure rate | 0 | 4 | 无效 structured response/LLM invocation |

Bad Case taxonomy 中目前已能回放多件装、多规格、赠品、数量歧义、单位歧义和标题噪声；第二件优惠、券后价、价格区间、SKU 混合文本、缺失信息、重复节点、popup/loading、动态价格仍未被当前数据集代表。详情见 `evaluation/reports/evaluation_v2.md`。

## 6. 模块依赖关系

```text
Runtime Port
  ├─ BrowserRuntime (DOM/ARIA) └─ Android Accessibility + DeviceBridge (polling)
  ↓
Observation / compressor / observation_id
  ↓
TaskOrchestrator → WorkflowEngine + Agent Router/Planner → ActionExecutor/SafetyGuard
  ↓
PlatformAdapter (Taobao / JD / Meituan / Mock)
  ↓
Hybrid Parser → NormalizedProduct → Comparison Engine / OfferCache
  ↓
SessionStore (InMemory / SQLite) 与 action lease/result lifecycle
```

平台专用 selector 没有泄漏到 BrowserRuntime；Runtime 不包含商品业务推理；安全判断位于确定性 executor/guard/bridge 层。

## 7. 同维度评分

| 维度 | 权重 | 分数 | 本轮证据依据 |
|---|---:|---:|---|
| requirements_and_core | 15% | 92 | Runtime、Observation、Workflow/Agent、Parser、Adapter、SessionStore、Safety 已实现并有回归 |
| architecture_and_explainability | 15% | 94 | Runtime/Adapter/Parser/Store 职责分离，统一 NormalizedProduct 契约 |
| safety | 15% | 90 | SafetyGuard、双重 observation_id、订单确认强制停止、Browser/Android 防线 |
| tests_and_builds | 15% | 90 | 132 tests、85% coverage、Python quality、Android test/build 通过；lint 阻断 |
| evaluation_credibility | 15% | 62 | schema/runner/Bad Case 可复现，但 0 人工复核、真实样本不足 |
| real_integration_readiness | 15% | 72 | 淘宝公开只读 smoke 已验证；Android runtime、JD/美团 live、真实 App 仍未验证 |
| engineering_governance | 5% | 78 | CI 四 job、Ruff/mypy/coverage/pre-commit/compile gate 已配置并本地通过；远端未运行、Android lint 阻断 |
| documentation | 5% | 98 | 本报告、JSON、README、阶段状态和面试说明均更新 |

加权计算：`92×0.15 + 94×0.15 + 90×0.15 + 90×0.15 + 62×0.15 + 72×0.15 + 78×0.05 + 98×0.05 = 83.8`，最终显示 **84/100**。

## 8. P0/P1/P2 剩余问题

### P0

- Android Emulator/AVD/system image 缺失，双向 Observation → action → Accessibility execution → callback 未完成 runtime 验证：`android-client/app/src/androidTest/.../DeviceBridgeRuntimeInstrumentedTest.kt`。
- 真实 Android shopping App 未验证；淘宝仅完成公开网页只读 smoke，JD/美团 live 未验证。
- Evaluation 没有 `HUMAN_VERIFIED` 样本，不能支撑真实复杂商品识别准确率。

### P1

- Android lint 需要可用的 `lint-gradle:31.5.2` 缓存/网络环境；SDK XML v4/v3 warning 与 Gradle deprecated warning 仍存在。
- GitHub Actions workflow 已配置但没有远端运行记录。
- Bad Case taxonomy 中仍有未代表类别，真实价格动态性和页面弹窗状态未纳入可信数据集。

### P2

- SQLite SessionStore 仍是本地单体实现，多进程 failover/生产吞吐未测量。
- BrowserRuntime 真实网页 selector fallback 需要更多独立、脱敏、可复现的页面样本。
- 真实模型调用、网络波动、长期价格变化和跨平台同品语义匹配仍未形成生产级基准。

## 9. 复验后结论

项目适合作为“安全模式跨平台 Computer-Use Agent 的离线工程原型 + 浏览器只读演示 + 淘宝公开页面只读 smoke”的面试 Demo。它不应被描述为已完成 Android Runtime、真实购物 App、全平台实时比价、真实模型准确率或生产交付。

