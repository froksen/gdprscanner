@echo off
chcp 65001 >nul
setlocal

echo.
echo  ================================================
echo       GDPR Scanner
echo  ================================================
echo.

rem --- Trin 1: Tjek Python ---
echo  [1/3] Tjekker Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  FEJL: Python blev ikke fundet.
    echo  Installer Python 3.8+ fra python.org
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo        %%v fundet
echo.

rem --- Trin 2: Virtuelt miljo ---
echo  [2/3] Forbereder virtuelt miljoe (.venv)...
if not exist ".venv\Scripts\python.exe" (
    echo        Opretter nyt venv...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo  FEJL: Kunne ikke oprette virtuelt miljoe.
        echo.
        pause
        exit /b 1
    )
    echo        Venv oprettet.
) else (
    echo        Venv findes allerede.
)

rem Kopier pythonw.exe til venv hvis den mangler
if not exist ".venv\Scripts\pythonw.exe" (
    for /f "tokens=*" %%p in ('python -c "import sys,os; print(os.path.dirname(sys.executable))"') do (
        if exist "%%p\pythonw.exe" copy "%%p\pythonw.exe" ".venv\Scripts\pythonw.exe" >nul
    )
)
echo.

rem --- Trin 3: Installer afhangigheder ---
echo  [3/3] Installerer afhaengigheder...
call .venv\Scripts\activate.bat
pip install -r requirements.txt -q --disable-pip-version-check
if errorlevel 1 (
    echo.
    echo  FEJL: Installation af afhaengigheder mislykkedes.
    echo.
    pause
    exit /b 1
)
echo        Alle afhaengigheder er klar.
echo.

rem --- Start programmet ---
echo  ================================================
echo       Starter GDPR Scanner i systembakken...
echo  ================================================
echo.
start "" "%~dp0.venv\Scripts\pythonw.exe" -m src.main

exit /b 0
