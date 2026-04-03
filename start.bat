@echo off
chcp 65001 >nul
setlocal

echo.
echo  ================================================
echo       GDPR Scanner
echo  ================================================
echo.

:: ── Trin 1: Tjek Python ────────────────────────────
echo  [1/3] Tjekker Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  FEJL: Python blev ikke fundet.
    echo  Installer Python 3.8+ fra https://python.org
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo         %%v fundet
echo.

:: ── Trin 2: Virtuelt miljø ─────────────────────────
echo  [2/3] Forbereder virtuelt miljoe (.venv)...
if not exist ".venv\Scripts\pythonw.exe" (
    echo         Opretter nyt venv...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo  FEJL: Kunne ikke oprette virtuelt miljoe.
        echo.
        pause
        exit /b 1
    )
    echo         Venv oprettet.
) else (
    echo         Venv findes allerede.
)
echo.

:: ── Trin 3: Installér afhængigheder ───────────────
echo  [3/3] Installerer afhaengigheder (requirements.txt)...
call .venv\Scripts\activate.bat
pip install -r requirements.txt -q --disable-pip-version-check
if errorlevel 1 (
    echo.
    echo  FEJL: Installation af afhaengigheder mislykkedes.
    echo.
    pause
    exit /b 1
)
echo         Alle afhaengigheder er klar.
echo.

:: ── Start programmet ───────────────────────────────
echo  ================================================
echo       Starter GDPR Scanner i systembakken...
echo  ================================================
echo.
start "" .venv\Scripts\pythonw.exe -m src.main

exit /b 0
