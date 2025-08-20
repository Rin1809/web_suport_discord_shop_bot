@echo off
setlocal

rem Lay duong dan cua thu muc chua script nay
set SCRIPT_DIR=%~dp0
rem Di chuyen ra thu muc cha (thu muc bot-dashboard)
cd /D "%SCRIPT_DIR%.."

rem Thiet lap cac bien
set VENV_NAME=moitruongao
set PYTHON_EXE_IN_VENV=%VENV_NAME%\Scripts\python.exe
set MAIN_SCRIPT=app.py

echo ===========================================================
echo Bot Dashboard Setup & Run Script for Windows
echo ===========================================================
echo Du an goc: %CD%
echo Moi truong ao: %VENV_NAME%
echo Script chinh: %MAIN_SCRIPT%
echo.

rem Kiem tra xem Python da duoc cai dat chua
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ===========================================================
    echo ERROR: Python khong duoc cai dat hoac khong tim thay trong PATH.
    echo Vui long cai dat Python va dam bao no da duoc them vao PATH.
    echo ===========================================================
    pause
    exit /b 1
)
echo Python da duoc tim thay.
echo.

rem Kiem tra va tao moi truong ao neu chua co
if not exist "%VENV_NAME%\Scripts\activate.bat" (
    echo ===========================================================
    echo Dang tao moi truong ao: %VENV_NAME%...
    echo ===========================================================
    python -m venv %VENV_NAME%
    if %errorlevel% neq 0 (
        echo ===========================================================
        echo ERROR: Tao moi truong ao that bai.
        echo Vui long kiem tra cai dat Python va quyen truy cap.
        echo ===========================================================
        pause
        exit /b 1
    )
    echo ===========================================================
    echo Moi truong ao da duoc tao thanh cong.
    echo ===========================================================
    echo.
) else (
    echo Moi truong ao '%VENV_NAME%' da ton tai.
    echo.
)

rem Kich hoat moi truong ao
echo ===========================================================
echo Dang kich hoat moi truong ao...
echo ===========================================================
call "%VENV_NAME%\Scripts\activate.bat"
if %errorlevel% neq 0 (
    echo ===========================================================
    echo ERROR: Kich hoat moi truong ao that bai.
    echo ===========================================================
    pause
    exit /b 1
)
echo Moi truong ao da duoc kich hoat.
echo.

rem Cai dat cac thu vien can thiet
echo ===========================================================
echo Dang cai dat cac thu vien tu requirements.txt...
echo ===========================================================
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ===========================================================
    echo ERROR: Cai dat thu vien that bai.
    echo Vui long kiem tra requirements.txt va ket noi mang.
    echo ===========================================================
    pause
    exit /b 1
)
echo Cac thu vien da duoc cai dat thanh cong.
echo.

rem Chay ung dung web
echo ===========================================================
echo Dang chay ung dung Bot Dashboard...
echo Ung dung se chay trong terminal nay.
echo De dung ung dung, nhan Ctrl+C trong cua so nay.
echo Ban co the truy cap giao dien web tai: http://127.0.0.1:5001
echo ===========================================================

rem Thuc thi script chinh trong terminal hien tai
rem Chu y: 'call' se giu cho cua so cmd mo va cho den khi script app.py ket thuc
call "%PYTHON_EXE_IN_VENV%" "%MAIN_SCRIPT%"

rem Xoa lenh timeout vi 'call' da giu cho den khi script xong
rem timeout /t 2 /nobreak > nul

endlocal
exit /b 0