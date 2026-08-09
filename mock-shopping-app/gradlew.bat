@echo off
setlocal
where gradle >nul 2>nul
if errorlevel 1 (
  echo Gradle was not found on PATH. Install Gradle or generate a standard Gradle wrapper.
  exit /b 1
)
gradle %*
endlocal
