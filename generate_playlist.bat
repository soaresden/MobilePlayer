@echo off
cd /d "%~dp0"

python -c "import os,json;fr=sorted([f for f in os.listdir('music') if f.lower().endswith('.mp3')]);sq=sorted([f for f in os.listdir('suno') if f.lower().endswith('.mp3')]) if os.path.isdir('suno') else [];jg=sorted([f for f in os.listdir('jingles') if f.lower().endswith('.mp3')]) if os.path.isdir('jingles') else [];open('playlist.js','w',encoding='utf-8').write('window.PLAYLIST_FR='+json.dumps(fr,ensure_ascii=False,indent=2)+';\nwindow.PLAYLIST_SQ='+json.dumps(sq,ensure_ascii=False,indent=2)+';');open('jingles.js','w',encoding='utf-8').write('window.JINGLES='+json.dumps(jg,ensure_ascii=False,indent=2)+';');print('OK:',len(fr),'FR,',len(sq),'SQ,',len(jg),'jingles')"
if not errorlevel 1 goto done

powershell -NoProfile -Command "$fr=Get-ChildItem 'music' -Filter *.mp3|Sort Name|%%{$_.Name};$sq=if(Test-Path 'suno'){Get-ChildItem 'suno' -Filter *.mp3|Sort Name|%%{$_.Name}}else{@()};$jg=if(Test-Path 'jingles'){Get-ChildItem 'jingles' -Filter *.mp3|Sort Name|%%{$_.Name}}else{@()};[IO.File]::WriteAllText((Join-Path(pwd)'playlist.js'),'window.PLAYLIST_FR='+($fr|ConvertTo-Json)+';\nwindow.PLAYLIST_SQ='+($sq|ConvertTo-Json)+';',[Text.Encoding]::UTF8);[IO.File]::WriteAllText((Join-Path(pwd)'jingles.js'),'window.JINGLES='+($jg|ConvertTo-Json)+';',[Text.Encoding]::UTF8);Write-Host 'OK:'$fr.Count'FR,'$sq.Count'SQ,'$jg.Count'jingles'"

:done
pause
