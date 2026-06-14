@echo off
cd /d "%~dp0"

python -c "import os,json;mp3s=sorted([f for f in os.listdir('music') if f.lower().endswith('.mp3')]);jdir='jingles';jingles=sorted([f for f in os.listdir(jdir) if f.lower().endswith('.mp3')]) if os.path.isdir(jdir) else [];open('playlist.js','w',encoding='utf-8').write('window.PLAYLIST='+json.dumps(mp3s,ensure_ascii=False,indent=2)+';');open('jingles.js','w',encoding='utf-8').write('window.JINGLES='+json.dumps(jingles,ensure_ascii=False,indent=2)+';');print('OK:',len(mp3s),'tracks,',len(jingles),'jingles')"
if not errorlevel 1 goto server

powershell -NoProfile -Command "$mp3s=Get-ChildItem 'music' -Filter *.mp3|Sort Name|%%{$_.Name};$jdir='jingles';$jingles=if(Test-Path $jdir){Get-ChildItem $jdir -Filter *.mp3|Sort Name|%%{$_.Name}}else{@()};[IO.File]::WriteAllText((Join-Path(pwd)'playlist.js'),'window.PLAYLIST='+($mp3s|ConvertTo-Json)+';',[Text.Encoding]::UTF8);[IO.File]::WriteAllText((Join-Path(pwd)'jingles.js'),'window.JINGLES='+($jingles|ConvertTo-Json)+';',[Text.Encoding]::UTF8);Write-Host 'OK:'$mp3s.Count'tracks,'$jingles.Count'jingles'"

:server
start "" "http://localhost:8080"
python -m http.server 8080
