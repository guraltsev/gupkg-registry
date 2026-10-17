@echo off
rem Validate the registry and list its packages.   _scripts\validate.cmd
setlocal EnableExtensions
call "%~dp0_python.cmd" || exit /b %ERRORLEVEL%
pushd "%REG_ROOT%"
%PY% _tools\validate_registry.py %*
set "RESULT=%ERRORLEVEL%"
popd
exit /b %RESULT%
