@echo off
cd /d "%~dp0"
echo Recuperation des paroles alignees depuis l'API Suno
echo (tu auras besoin de coller ton token Bearer depuis DevTools)
echo.
python fetch_suno_lrc.py
pause
