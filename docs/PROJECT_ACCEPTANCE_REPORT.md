# PriceSight 项目全面验收报告

验收日期：2026-08-09

## 一、验收结论

综合评分：**65/100**。

验收结论：**离线工程原型有条件通过；真实设备、真实平台与生产交付不通过。**

当前项目已经形成完整、可解释、可测试的离线技术闭环，适合作为技术演示、面试项目和后续真实设备开发的基线。但 Android client 与后端尚未形成真实双向动作闭环，没有真实购物 App adapter、真实设备运行、真实模型验证和生产工程治理，因此不能按“可上线产品”或“真实跨平台比价 Agent”验收。

## 二、评分模型

| 维度 | 权重 | 得分 | 结论 |
|---|---:|---:|---|
| 需求覆盖与核心能力 | 15% | 78 | 阶段0至13的大部分离线里程碑有代码和测试，但真实平台阶段未完成 |
| 架构与可解释性 | 15% | 84 | 模块边界清晰，Workflow + Agent + Action Harness 路径可解释 |
| 安全设计 | 15% | 80 | SAFE MODE 和确定性停止存在，但真实动作通道未接入，安全词表覆盖有限 |
| 测试与构建质量 | 15% | 74 | 后端与两个 Android 工程通过测试/构建；缺 coverage、lint、type check 和 CI |
| Evaluation 可信度 | 15% | 52 | 原始报告可复现，但样本少、均为 synthetic/Mock、任务重复度高 |
| 真实集成与运行就绪度 | 15% | 30 | 无真实设备闭环、真实 App、真实 adapter、live LLM 和真实网络测量 |
| 工程治理与交付 | 5% | 20 | 仓库零提交、全部文件未跟踪，无 CI/pre-commit；验收时已修正报告忽略规则 |
| 文档与可沟通性 | 5% | 90 | 中文文档、阶段报告、架构、面试和审计材料较完整 |
| **加权总分** | **100%** | **65** | **离线原型有条件通过** |

评分不是生产质量认证，只用于说明当前代码库相对于项目目标的实际成熟度。

## 三、本次实际验证

工程规模基线：81 个 Python 文件、约 4616 行 Python；13 个 Kotlin 文件、约 745 行 Kotlin；后端包含 20 个测试文件。该统计包含测试代码，不代表有效业务代码行数。

| 验证项 | 命令/证据 | 结果 |
|---|---|---|
| 后端测试 | `.venv\Scripts\python.exe -m pytest -q` | **79 passed，1 warning，0.54s** |
| Python 编译检查 | `python -m compileall -q backend\app scripts` | **通过** |
| Android client 测试 | Gradle `test --offline` | **BUILD SUCCESSFUL**；2 个唯一 JVM 测试在 debug/release 各执行一次 |
| Android client APK | Gradle `assembleDebug --offline` | **BUILD SUCCESSFUL**；APK 存在 |
| Mock App 测试 | Gradle `test --offline` | **BUILD SUCCESSFUL**；1 个唯一 JVM 测试在 debug/release 各执行一次 |
| Mock App APK | Gradle `assembleDebug --offline` | **BUILD SUCCESSFUL**；APK 存在 |
| 阶段3、7至12 runners | 7 个脚本 | **全部通过并刷新报告** |
| 最终 Evaluation | `scripts/run_final_evaluation.py` | **通过并刷新阶段13报告** |
| 敏感信息模式扫描 | `rg` 密钥/密码/私钥模式 | 未发现真实密钥；命中仅为测试占位符和配置代码 |
| Android lint | Gradle `lintDebug --offline` | **未完成**；本地未缓存 `lint-gradle:31.5.2`，不是代码诊断结果 |

构建仍报告：Gradle 10 不兼容的弃用特性，以及 Android SDK XML v4/v3 工具链兼容警告。

## 四、最终 Evaluation 复核

刷新后的 [phase13_final_evaluation.json](../evaluation/reports/phase13_final_evaluation.json) 记录：

| 指标 | 最新值 | 有效范围 |
|---|---:|---|
| Tree compression retained ratio mean | 0.5714 | 5 个非空 synthetic fixture |
| Rule-only parsing accuracy | 1.0 | 8 个 synthetic、未人工复核样本 |
| Hybrid parsing accuracy | 1.0 | 8 个 synthetic、FakeLLM |
| Task success rate | 1.0 | 10 次相同 Mock E2E 场景 |
| Action success rate | 1.0 | Mock E2E 中实际进入 executor 的动作 |
| Average retries / steps / LLM calls | 0.0 / 13.0 / 1.0 | 10 次 Mock E2E |
| End-to-end latency mean | 7.8086 ms | 本机 Python Mock Device |
| Warm cache hit rate | 1.0 | 两个 fixture source 的第二次比较 |
| Safety stop accuracy | 1.0 | 重复执行同一安全停止场景 |
| Polling latency mean | 1.8174 ms | fake transport benchmark |
| Event latency mean | 29.1859 ms | fake transport + Windows 稳定化调度 |

这些数字能证明 runner 可复现和受控流程稳定，不能证明真实平台准确率、真实 Agent 泛化能力或 event transport 优于 polling。

## 五、已验收通过的能力

### 1. 模块化架构

Observation、Action、Workflow、Agent、LLM、Parser、Platform、Comparison、Cache 和 Transport 责任分离。领域逻辑没有集中堆积在 FastAPI 入口中。

### 2. Action Harness

实现 resource ID、node ID、文本、归一化语义、fuzzy 和 fresh bounds 的分层匹配；使用 `observation_id` 防止 stale UI；动作后重新观察并验证状态。

### 3. Workflow + Agent

确定性步骤由 YAML Workflow 执行，歧义步骤交给结构化 Agent。Planner 有 schema、置信度和预算限制，Fake provider 使离线测试不依赖密钥。

### 4. SAFE MODE

订单、支付、密码、验证码和身份验证文本会触发确定性停止；未 opt-in 的购物车动作会被阻止。安全规则位于代码中，不只存在于 Prompt。

### 5. Mock E2E 与报告

Mock 场景覆盖搜索、Agent 选择、规格、优惠、购物车、最终价和订单确认前停止。原始结果由 runner 生成，并明确标注 synthetic/Mock 范围。

## 六、关键缺口与风险

### P0——阻断真实交付

1. **无 Git 基线。** `git status` 显示 `No commits yet on master`，所有文件未跟踪。当前无法审计版本、回滚、比较变更或建立 CI 基线。
2. **Android—Backend 动作闭环未接通。** Android service 只通过 HTTP POST 导出 observation；`AndroidActionExecutor` 没有在 service 中实例化，也没有后端 action command channel。
3. **后端 observation endpoint 不保存状态。** `/observations` 只返回确认；全局 WebSocket `event_transport` 与 dependency container 不共用同一实例，`TRANSPORT_MODE` 不能形成真实应用运行路径。
4. **Android 没有 WebSocket event client。** 阶段12的 event transport 只有后端队列和契约测试。
5. **本地 HTTP 运行风险。** Android target SDK 34，默认 endpoint 为 `http://10.0.2.2:8000/observations`，Manifest 没有 debug network-security 配置；真实导出尚未验证。
6. **无真实平台 adapter。** Meituan、JD、Taobao 均没有脱敏 fixture、selector、真实 page detection 或设备验证。

### P1——阻断高可信质量结论

1. 后端无 coverage 门槛、lint、静态类型检查、pre-commit 和 CI。
2. Android client 只有 2 个唯一 JVM 测试，Mock App 只有 1 个唯一 JVM 测试；没有 instrumented/UI test。
3. Parser dataset 只有 8 个 synthetic 样本，未人工复核。
4. 10 次任务 benchmark 重复同一条 Mock 路径，不能评估泛化、恢复和 Bad Case 分布。
5. SafetyGuard 主要依赖中英文 substring 词表，缺少更多页面语义、动作类型和对抗式变体测试。
6. WebSocket 无认证、session/device identity、消息大小限制、背压、断线恢复和生命周期管理。

### P2——工程完善项

1. 解决 Gradle 10 弃用和 SDK XML 工具链兼容警告。
2. 增加 Android lint 依赖并纳入 CI。
3. 为 SQLite cache 增加并发、损坏恢复和多进程策略，或明确限制为单进程开发缓存。
4. provider client 增加显式关闭、重试策略、速率限制和可观测性。
5. 使用真实设备条件重新设计 polling/event benchmark，报告稳定化开销、分位数和失败率。

## 七、工程治理检查

| 项目 | 状态 |
|---|---|
| Git commit 基线 | 缺失 |
| CI workflow | 缺失 |
| Ruff/Flake8 | 缺失 |
| mypy/pyright | 缺失 |
| Coverage threshold | 缺失 |
| pre-commit | 缺失 |
| Docker/部署说明 | 缺失，但当前离线原型可接受 |
| `.env.example` | 验收时已补齐当前配置项 |
| Evaluation JSON 可纳入 Git | 验收时已修正 `.gitignore` |
| 中文文档与相对链接 | 完整，链接检查通过 |

## 八、建议验收门槛

### 可展示原型

当前代码已达到，但应先创建 Git 初始基线并保留本报告。

### 真实设备开发版

必须完成：后端 action API/WebSocket session、Android 双向 transport、真实 action executor 装配、模拟器或设备 E2E、网络安全配置和至少一个真实脱敏 adapter。

### 对外发布或生产版

必须进一步完成：认证授权、设备身份、CI、lint/type/coverage、持久日志、隐私处理、真实评估集、故障恢复、负载/安全测试和运维方案。

## 九、最终判定

- **离线技术演示：通过。**
- **面试项目：通过，前提是明确说明 synthetic/Mock 范围。**
- **真实设备开发基线：有条件通过，需先完成 P0 闭环。**
- **真实跨平台比价能力：不通过/未实现。**
- **生产上线：不通过。**

本报告替代此前偏阶段完成度的单一结论，作为 2026-08-09 的项目级验收基线。

机器可读版本见 [project_acceptance_2026-08-09.json](../evaluation/reports/project_acceptance_2026-08-09.json)。
