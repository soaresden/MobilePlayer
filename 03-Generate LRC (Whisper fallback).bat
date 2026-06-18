@echo off
cd /d "%~dp0"
echo Transcription Whisper → génération des fichiers .lrc dans music\
echo (première fois : téléchargement du modèle ~1.4 Go)
echo.
python generate_lrc.py
pause
