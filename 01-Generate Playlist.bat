@echo off
cd /d "%~dp0"
echo Génération de playlist.js et jingles.js...

python -c "import os,json;pl=sorted([f for f in os.listdir('music') if f.lower().endswith('.mp3')]);jg=sorted([f for f in os.listdir('jingles') if f.lower().endswith('.mp3')]) if os.path.isdir('jingles') else [];open('playlist.js','w',encoding='utf-8').write('window.PLAYLIST='+json.dumps(pl,ensure_ascii=False,indent=2)+';\n');open('jingles.js','w',encoding='utf-8').write('window.JINGLES='+json.dumps(jg,ensure_ascii=False,indent=2)+';\n');print('OK:',len(pl),'morceaux,',len(jg),'jingles')"
if not errorlevel 1 goto done

powershell -NoProfile -Command "$pl=Get-ChildItem 'music' -Filter *.mp3|Sort Name|%%{$_.Name};$jg=if(Test-Path 'jingles'){Get-ChildItem 'jingles' -Filter *.mp3|Sort Name|%%{$_.Name}}else{@()};[IO.File]::WriteAllText((Join-Path(pwd)'playlist.js'),'window.PLAYLIST='+($pl|ConvertTo-Json -Compress)+";\n",[Text.Encoding]::UTF8);[IO.File]::WriteAllText((Join-Path(pwd)'jingles.js'),'window.JINGLES='+($jg|ConvertTo-Json -Compress)+";\n",[Text.Encoding]::UTF8);Write-Host 'OK:'$pl.Count'morceaux,'$jg.Count'jingles'"

:done
pause
