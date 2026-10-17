@echo off
rem Internal helper: select Python and the gupkg checkout.   call "%~dp0_python.cmd"  ->  PY, REG_ROOT, GUPKG_REPO
rem GUPKG_REPO may be set beforehand; otherwise the folder holding this checkout, then a sibling "gupkg".
for %%I in ("%~dp0..") do set "REG_ROOT=%%~fI"
if not defined GUPKG_REPO if exist "%REG_ROOT%\..\src\gupkg\cli.py" for %%I in ("%REG_ROOT%\..") do set "GUPKG_REPO=%%~fI"
if not defined GUPKG_REPO if exist "%REG_ROOT%\..\gupkg\src\gupkg\cli.py" for %%I in ("%REG_ROOT%\..\gupkg") do set "GUPKG_REPO=%%~fI"
if not defined GUPKG_REPO (
    >&2 echo [scripts] Cannot find the gupkg repository. Set GUPKG_REPO to its folder.
    exit /b 1
)
set "PY="
if exist "%GUPKG_REPO%\.venv\Scripts\python.exe" set "PY="%GUPKG_REPO%\.venv\Scripts\python.exe""
if not defined PY if exist "%GUPKG_REPO%\src\gupkg\python\python.exe" set "PY="%GUPKG_REPO%\src\gupkg\python\python.exe""
if not defined PY (
    py -3 -c "import sys" >nul 2>nul
    if not errorlevel 1 set "PY=py -3"
)
if not defined PY (
    >&2 echo [scripts] No Python found in the gupkg checkout or on PATH.
    exit /b 9009
)
exit /b 0
