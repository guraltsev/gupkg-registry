@echo off
rem Run gupkg's registry tool on this checkout.   _scripts\registry-tool.cmd update|pin|validate [options]
rem Needs network access for update and pin. Nothing is committed or pushed without --auto-push.
setlocal EnableExtensions
call "%~dp0_python.cmd" || exit /b %ERRORLEVEL%
pushd "%REG_ROOT%"
%PY% _tools\registry_tool.py %*
set "RESULT=%ERRORLEVEL%"
popd
exit /b %RESULT%
