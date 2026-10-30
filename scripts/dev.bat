@echo off
rem Phase 2 dev loop: engine in one window, overlay in another. Run from the repo root.
rem   scripts\dev.bat                                   YouTube clone with your pins (cache\pins\)
rem   scripts\dev.bat tutorials\mug-solidworks.md
rem   scripts\dev.bat replay                            overlay only, plays the recorded fixture (no engine)
setlocal
cd /d "%~dp0.."
if /i "%~1"=="replay" (
  cd overlay
  if not exist node_modules call npm install
  call npm run replay
  goto :eof
)
set TUT=%~1
if "%TUT%"=="" set TUT=tutorials\youtube-clone-vscode.md
start "GhostGuide engine" cmd /k py -m engine play %TUT% %2 %3 %4
cd overlay
if not exist node_modules call npm install
call npm start
