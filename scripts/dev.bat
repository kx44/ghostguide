@echo off
rem Engine in one window, overlay in another. Run from the repo root.
rem   scripts\dev.bat                                   the YouTube clone tutorial
rem   scripts\dev.bat tutorials\mug-solidworks.md       any tutorial; add --restart to start over, --window "part of a title"
rem   scripts\dev.bat nogpu tutorials\x.md              model checks off for this run: no Glimmer GPU, no paid step checks
rem   scripts\dev.bat import                            nothing loaded: opens the import window
rem   scripts\dev.bat replay                            overlay only, plays the recorded fixture (no engine)
setlocal
cd /d "%~dp0.."
if /i "%~1"=="nogpu" (
  set CHECK_MODELS=off
  shift
)
if /i "%~1"=="replay" (
  cd overlay
  if not exist node_modules call npm install
  call npm run replay
  goto :eof
)
if /i "%~1"=="import" (
  start "GhostGuide engine" cmd /k py -m engine play
  cd overlay
  if not exist node_modules call npm install
  call npm start -- --import
  goto :eof
)
set TUT=%~1
if "%TUT%"=="" set TUT=tutorials\youtube-clone-vscode.md
start "GhostGuide engine" cmd /k py -m engine play %TUT% %2 %3 %4 %5
cd overlay
if not exist node_modules call npm install
call npm start
