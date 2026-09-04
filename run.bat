@echo off
setlocal EnableExtensions DisableDelayedExpansion
:: protect cwd
pushd

:: Dynamically find poetry.exe
set "myPoetry="
for /f "delims=" %%i in ('where poetry.exe 2^>nul') do (
    set "myPoetry=%%i"
    goto :found_poetry
)

:found_poetry
:: Check if poetry was actually found
if "%myPoetry%"=="" (
    echo [ERROR] poetry.exe could not be found in your system PATH.
    exit /b 1
)

:: script is at proj_root/
cd /d %~dp0
for %%I in (%cd%) do set myServName=%%~nxI
%myPoetry% run python src\cli.py %*
if NOT %errorlevel% == 0 (
	goto :fail
)
popd
goto :EOF

:fail
popd

