@echo off
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 (set PY=python) else (set PY=py)
%PY% -m pip install -r requirements.txt
%PY% -m streamlit run simulador.py --theme.base dark
pause


