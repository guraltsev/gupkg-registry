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
rem Run gupkg's registry tool on this checkout.   _scripts\registry-tool.cmd update|pin|validate [options]
rem Needs network access for update and pin. Nothing is committed or pushed without --auto-push.
setlocal EnableExtensions
call "%~dp0_python.cmd" || exit /b %ERRORLEVEL%
pushd "%REG_ROOT%"
%PY% _tools\registry_tool.py %*
set "RESULT=%ERRORLEVEL%"
popd
exit /b %RESULT%
