@echo off
cd /d "%~dp0"
echo.
echo  AlbaFrancia FM — Paroles brutes depuis Suno (pistes 8 a 32)
echo  Les 7 premiers .lrc ne seront PAS modifies.
echo.
python fetch_suno_plain.py
echo.
pause
