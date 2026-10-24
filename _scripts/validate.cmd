@echo off
rem Validate the whole registry: the package checker on every directory, then the registry rules.   _scripts\validate.cmd
setlocal EnableExtensions
call "%~dp0_python.cmd" || exit /b %ERRORLEVEL%
pushd "%REG_ROOT%"
%PY% _tools\pkg_check.py --all
set "RESULT=%ERRORLEVEL%"
if "%RESULT%"=="0" (
    %PY% _tools\registry_tool.py validate
    set "RESULT=%ERRORLEVEL%"
)
popd
exit /b %RESULT%
