@echo off
title LocalAPI - Claude Code Proxy
echo Starting LocalAPI proxy...

:: Configuration (edit these)
set PROXY_PORT=8000
set OPENCODE_PORT=4096
set DEFAULT_MODEL=localapi/mimo-v2.5-free

:: Start the proxy server
start /min "" python "%~dp0server.py"

:: Wait for server to be ready
echo Waiting for proxy on port %PROXY_PORT%...
timeout /t 2 /nobreak >nul

:: Verify proxy is up
curl -s http://localhost:%PROXY_PORT%/health >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Proxy failed to start. Check if port %PROXY_PORT% is in use.
    pause
    exit /b 1
)

echo.
echo Proxy ready at http://localhost:%PROXY_PORT%/v1
echo Model: %DEFAULT_MODEL%
echo.
echo Use in opencode: model "%DEFAULT_MODEL%"
echo Or set OPENAI_API_BASE=http://localhost:%PROXY_PORT%/v1 for Claude Code
echo.
pause
