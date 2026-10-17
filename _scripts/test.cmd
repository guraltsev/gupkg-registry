@echo off
rem Run the registry's consistency tests.   _scripts\test.cmd [pytest arguments]
setlocal EnableExtensions
call "%~dp0_python.cmd" || exit /b %ERRORLEVEL%
%PY% -c "import pytest" >nul 2>nul
if errorlevel 1 (
    >&2 echo [scripts] pytest is not installed for this Python; use the gupkg checkout's .venv.
    exit /b 1
)
pushd "%REG_ROOT%"
%PY% -m pytest -q %*
set "RESULT=%ERRORLEVEL%"
popd
exit /b %RESULT%
