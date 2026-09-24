@echo off
setlocal EnableExtensions

pushd "%~dp0.." >nul
if errorlevel 1 goto :fail

set "PYTHON_CMD="
where py >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD (
    where python >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    where winget >nul 2>&1
    if errorlevel 1 (
        echo Error: Python is missing and winget is not available.
        echo Install Python 3.11 or newer, then run this script again.
        goto :fail
    )
    winget install --id Python.Python.3.11 -e --accept-source-agreements --accept-package-agreements
    if errorlevel 1 goto :fail
    where py >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=py -3"
)

if not defined PYTHON_CMD (
    echo Error: Python was installed but is not available in this shell.
    echo Open a new terminal and run ci\setup.bat again.
    goto :fail
)

%PYTHON_CMD% -m pip --version >nul 2>&1
if errorlevel 1 %PYTHON_CMD% -m ensurepip --upgrade
if errorlevel 1 goto :fail

where poetry >nul 2>&1
if errorlevel 1 %PYTHON_CMD% -m pip install --user poetry
if errorlevel 1 goto :fail

where tesseract >nul 2>&1
if errorlevel 1 (
    where winget >nul 2>&1
    if errorlevel 1 (
        echo Error: Tesseract is missing and winget is not available.
        echo Install Tesseract OCR, then run this script again.
        goto :fail
    )
    winget install --id UB-Mannheim.TesseractOCR -e --accept-source-agreements --accept-package-agreements
    if errorlevel 1 goto :fail
)

%PYTHON_CMD% -m poetry install
if errorlevel 1 goto :fail

echo Setup complete. Use ci\run.bat for bstier commands.
popd >nul
exit /b 0

:fail
set "exit_code=%ERRORLEVEL%"
if "%exit_code%"=="0" set "exit_code=1"
popd >nul
exit /b %exit_code%