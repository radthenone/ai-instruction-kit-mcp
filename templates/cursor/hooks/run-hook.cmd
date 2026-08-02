@echo off
REM Cursor hook launcher (Windows): non-interactive Git Bash, no leftover console.
REM Usage: run-hook.cmd gate-destructive.sh
setlocal EnableExtensions
set "SCRIPT=%~dp0%~1"
if "%~1"=="" (
  echo {"permission":"deny","user_message":"run-hook.cmd: brak nazwy skryptu","agent_message":"Hook launcher: missing script name"}
  exit /b 1
)
if not exist "%SCRIPT%" (
  echo {"permission":"deny","user_message":"run-hook.cmd: brak pliku hooka","agent_message":"Hook launcher: script not found"}
  exit /b 1
)

set "BASH_EXE="
where bash >nul 2>&1 && for /f "delims=" %%i in ('where bash') do (
  set "BASH_EXE=%%i"
  goto :found_bash
)
if exist "%ProgramFiles%\Git\bin\bash.exe" set "BASH_EXE=%ProgramFiles%\Git\bin\bash.exe"
if not defined BASH_EXE if exist "%ProgramFiles%\Git\usr\bin\bash.exe" set "BASH_EXE=%ProgramFiles%\Git\usr\bin\bash.exe"
if not defined BASH_EXE if exist "%LOCALAPPDATA%\Programs\Git\bin\bash.exe" set "BASH_EXE=%LOCALAPPDATA%\Programs\Git\bin\bash.exe"

:found_bash
if not defined BASH_EXE (
  echo {"permission":"deny","user_message":"Hook: brak bash (zainstaluj Git for Windows)","agent_message":"Hook launcher: Git Bash not found in PATH"}
  exit /b 1
)

"%BASH_EXE%" --noprofile --norc "%SCRIPT%"
exit /b %ERRORLEVEL%
