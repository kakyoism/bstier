@echo off
setlocal EnableExtensions

pushd "%~dp0.." >nul
set "POETRY_CMD=poetry"
where poetry >nul 2>&1
if errorlevel 1 (
    where py >nul 2>&1
    if errorlevel 1 (
        echo Error: Poetry is not installed. Run ci\setup.bat first.
        popd >nul
        exit /b 1
    )
    set "POETRY_CMD=py -3 -m poetry"
)

%POETRY_CMD% run bstier %*
set "exit_code=%ERRORLEVEL%"
popd >nul
exit /b %exit_code%
