@echo off
REM ============================================================================
REM HudAutoTest 启动脚本（Windows）
REM ----------------------------------------------------------------------------
REM 用法：
REM   run.bat            启动 GUI
REM   run.bat --check    仅环境自检
REM ============================================================================
setlocal
cd /d "%~dp0"

if "%PYTHON_BIN%"=="" set PYTHON_BIN=python

where %PYTHON_BIN% >nul 2>nul
if errorlevel 1 (
    echo [错误] 未找到 %PYTHON_BIN%，请安装 Python 并加入 PATH
    exit /b 1
)

%PYTHON_BIN% -c "import tkinter" >nul 2>nul
if errorlevel 1 (
    echo [错误] 缺少 tkinter（请使用官方 Python 安装包，勾选 tcl/tk）
    exit /b 1
)

if "%~1"=="--check" (
    %PYTHON_BIN% tools\check_env.py
    exit /b %errorlevel%
)

echo [信息] 启动 HudAutoTest ...
%PYTHON_BIN% main.py %*
endlocal
