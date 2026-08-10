# 环境与复现

## 本机约定

项目与非必要工具优先放在 F 盘：

- 项目：`F:\projects_2027\PriceSight`
- Python：`D:\python\python.exe`，3.12.1
- Android SDK：`F:\newinstall\android_sdk`
- platform-tools：`F:\newinstall\android_sdk\platform-tools`
- cmdline-tools：`F:\newinstall\android_sdk\cmdline-tools\latest\bin`
- platforms：`F:\newinstall\android_sdk\platforms\android-34`
- build-tools：`F:\newinstall\android_sdk\build-tools\34.0.0`
- Gradle：`F:\newinstall\gradle-9.7.0-bin\gradle-9.7.0`

具体 JDK 以当前机器 `JAVA_HOME` 和 Android 构建输出为准；Android 模块使用 API 34 / Gradle 9.7 兼容配置。

## Python

```powershell
uv sync
uv run pytest
uv run ruff check backend
uv run mypy backend/app backend/tests
```

## Android / Mock App

```powershell
.\android-client\gradlew.bat test
.\android-client\gradlew.bat assembleDebug
.\mock-shopping-app\gradlew.bat test
.\mock-shopping-app\gradlew.bat assembleDebug
```

Emulator runtime 证据使用专用 AVD 和 External Harness。模拟器访问宿主机 backend 时使用 Android Emulator 的 `10.0.2.2` 映射，并保持正常安全策略；没有 Emulator/设备时只能标记 BLOCKED 或 BUILD_ONLY。

## 证据与限制

首次阶段曾遇到 adb、SDK、Gradle 或物理设备缺失；这些阻断及解除过程见 [开发历史](03-development-history.md)。CI/build 成功只证明编译或测试命令成功，不自动升级为 Runtime Verified。不得在未执行真实网页或真实 App 时作相应声明。
