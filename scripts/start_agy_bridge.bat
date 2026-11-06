@echo off
chcp 65001 >nul
title AIVideo Antigravity CLI Bridge (:8099)
echo ========================================================
echo  AIVideo - Antigravity CLI (agy) Host Bridge
echo  監聽埠: 8099 (供 Docker aivideo-pipeline 容器呼叫)
echo  生圖模型: Antigravity CLI (Pro 免金鑰)
echo ========================================================
python -u "%~dp0agy_bridge.py"
pause

