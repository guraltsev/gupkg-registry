@echo off
if defined GUPKG_IN_SCRIPT goto :main
set "GUPKG_IN_SCRIPT=1"
call "%~f0" %*
set "GUPKG_RC=%ERRORLEVEL%"
set "GUPKG_IN_SCRIPT="
rem A script a person starts waits for a key so its window stays readable; GUPKG_NO_PAUSE turns that off (tests, other scripts).
if not defined GUPKG_NO_PAUSE pause
exit /b %GUPKG_RC%
:main
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
