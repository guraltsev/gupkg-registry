@echo off
rem Put gupkg-tui.cmd (gupkg's src\package-tui.cmd) in every package.   _scripts\sync-launchers.cmd [--check]
setlocal EnableExtensions
call "%~dp0_python.cmd" || exit /b %ERRORLEVEL%
pushd "%REG_ROOT%"
%PY% _tools\sync_package_launchers.py %*
set "RESULT=%ERRORLEVEL%"
popd
exit /b %RESULT%
