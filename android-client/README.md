# PriceSight Android 客户端

这是阶段2的设备侧 MVP。客户端通过 `AccessibilityService` 采集当前窗口，将树转换为 framework-neutral DTO，显示调试状态，并异步把 JSON observation 导出到后端。

## 启用服务

1. 将 debug APK 安装到测试设备或模拟器。
2. 打开应用。
3. 点击“打开无障碍设置”。
4. 启用“PriceSight Android”。

Activity 会显示服务状态、当前 package、节点数量和最新 observation 时间。

## 本地 HTTP 导出

默认 endpoint：

```text
http://10.0.2.2:8000/observations
```

该地址用于 Android 模拟器访问宿主机 FastAPI。USB 设备需要可达的宿主机地址；如果 adb 可用，可以使用 `adb reverse tcp:8000 tcp:8000`。

后端 endpoint 目前只返回调试确认，不执行动作，也不存储私人数据。

## 构建

```powershell
.\gradlew.bat test
.\gradlew.bat assembleDebug
```

`gradlew.bat` 委托给本机 Gradle。项目环境已配置 Gradle 9.7.0、Android API 34 和 build-tools 34.0.0；JVM 测试和 `assembleDebug` 曾通过。构建可能产生非致命 Gradle 弃用和 SDK XML 兼容警告。

## 安全边界

客户端只观察 Accessibility 节点并导出序列化 observation，不包含支付、下单、验证码绕过、账号注册或购买确认逻辑。
