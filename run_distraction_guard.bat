@echo off
title Focus Guard - Anti-Distraction Daemon
echo ==========================================================
echo Starting Focus Guard...
echo Automatically closes TikTok and distraction feeds.
echo ==========================================================
cd /d "%~dp0"
python distraction_guard.py
pause
