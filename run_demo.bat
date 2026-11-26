@echo off
rem DocSense demo launcher (Windows): double-click this file.
rem ASCII only on purpose - Korean text inside .bat files breaks on some cmd code pages and closes the window.
cd /d "%~dp0"

set "PY=python"
where python >nul 2>nul || set "PY=py -3"

rem Install only when it has not finished before (no streamlit.exe = install again)
if not exist ".venv\Scripts\streamlit.exe" (
    echo [1/2] First run: creating .venv and installing packages. This takes a few minutes...
    %PY% -m venv .venv || goto :fail
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :fail
)
if not exist ".env" copy ".env.example" ".env" >nul

rem Streamlit asks for an e-mail on its very first run and waits for Enter - skip that question
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    if not exist "%USERPROFILE%\.streamlit" mkdir "%USERPROFILE%\.streamlit"
    > "%USERPROFILE%\.streamlit\credentials.toml" (
        echo [general]
        echo email = ""
    )
)

echo [2/2] Starting the demo. If the browser does not open, go to http://localhost:8501
echo Close this window to stop the demo.
".venv\Scripts\python.exe" -m streamlit run app\main.py
echo.
echo Demo stopped. Read the messages above if it stopped by itself.
pause
exit /b

:fail
echo.
echo Setup failed. Check that Python 3.10 or newer is installed: open a terminal and type  python --version
echo If it opens Microsoft Store, install Python from python.org and tick "Add python.exe to PATH".
pause
