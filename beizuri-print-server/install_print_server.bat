@echo off
echo ========================================
echo BeiZuri Print Server Installation
echo ========================================
echo.

cd /d "%~dp0"

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo This script requires Administrator privileges!
    echo Please right-click and select "Run as Administrator"
    pause
    exit /b 1
)

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed!
    pause
    exit /b 1
)

echo Python found!
python --version
echo.

REM Check Python architecture
for /f "delims=" %%i in ('python -c "import struct; print('64-bit' if struct.calcsize('P') * 8 == 64 else '32-bit')"') do set PYTHON_ARCH=%%i
echo Python Architecture: %PYTHON_ARCH%
echo.

if not exist "requirements.txt" (
    echo ERROR: requirements.txt not found in %cd%
    pause
    exit /b 1
)

echo Installing dependencies...
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies!
    pause
    exit /b 1
)

echo.
echo ========================================
echo Checking USB Backend (libusb)
echo ========================================
echo.

if not exist "libusb-1.0.dll" (
    echo WARNING: libusb-1.0.dll not found!
    echo.
    echo The print server needs libusb to communicate with USB printers.
    echo.
    echo Please choose an option:
    echo   1. I will use Zadig to install WinUSB driver (RECOMMENDED)
    echo   2. I have libusb-1.0.dll and will copy it manually
    echo   3. Continue anyway (service may not work)
    echo.
    set /p usb_choice="Select [1-3]: "
    
    if "!usb_choice!"=="1" (
        echo.
        echo RECOMMENDED SOLUTION - Using Zadig:
        echo ========================================
        echo 1. Download Zadig from: https://zadig.akeo.ie/
        echo 2. Run Zadig as Administrator
        echo 3. Go to Options - Check "List All Devices"
        echo 4. Select your thermal printer from the dropdown
        echo 5. Select "WinUSB" as the target driver
        echo 6. Click "Install Driver" or "Replace Driver"
        echo 7. Come back and run this script again
        echo ========================================
        echo.
        echo Opening Zadig website in your browser...
        start https://zadig.akeo.ie/
        echo.
        echo After installing the driver with Zadig, run this script again.
        pause
        exit /b 0
    )
    
    if "!usb_choice!"=="2" (
        echo.
        echo Please follow these steps:
        echo ========================================
        echo 1. Download libusb from: https://github.com/libusb/libusb/releases
        echo 2. Download libusb-1.0.29.7z
        echo 3. Extract it using 7-Zip
        echo 4. For %PYTHON_ARCH% Python:
        if "%PYTHON_ARCH%"=="64-bit" (
            echo    - Copy from: VS2019\MS64\dll\libusb-1.0.dll
        ) else (
            echo    - Copy from: VS2019\MS32\dll\libusb-1.0.dll
        )
        echo 5. Paste libusb-1.0.dll into: %cd%
        echo 6. Run this script again
        echo ========================================
        echo.
        echo Opening GitHub releases page...
        start https://github.com/libusb/libusb/releases
        pause
        exit /b 0
    )
    
    echo.
    echo WARNING: Continuing without libusb-1.0.dll
    echo The service may fail with "No backend available" error
    echo.
    timeout /t 3
) else (
    echo ✓ Found libusb-1.0.dll
)

echo.
echo Creating printer config file if not exists...
if not exist "printer_config.json" (
    (
    echo {
    echo   "vendor_id": "0x0483",
    echo   "product_id": "0x5743",
    echo   "out_endpoint": "0x01"
    echo }
    ) > printer_config.json
)

echo.
echo Downloading NSSM for Windows Service...
if not exist nssm.exe (
    powershell -Command "Invoke-WebRequest -Uri 'https://nssm.cc/release/nssm-2.24.zip' -OutFile 'nssm.zip' -UseBasicParsing"
    if %errorlevel% neq 0 (
        echo Failed to download NSSM.
        pause
        exit /b 1
    )
    powershell -Command "Expand-Archive -Path 'nssm.zip' -DestinationPath '.' -Force"
    copy nssm-2.24\win64\nssm.exe nssm.exe
    rmdir /s /q nssm-2.24
    del nssm.zip
)

echo.
echo Stopping and removing old service if exists...
sc query BeiZuriPrintServer >nul 2>&1
if %errorlevel% equ 0 (
    net stop BeiZuriPrintServer >nul 2>&1
    timeout /t 2 /nobreak >nul
    nssm remove BeiZuriPrintServer confirm
    timeout /t 2 /nobreak >nul
)

echo.
echo Installing BeiZuri Print Service...
set PYTHON_PATH=
for /f "delims=" %%i in ('where python') do set PYTHON_PATH=%%i

if "%PYTHON_PATH%"=="" (
    echo ERROR: Could not find Python executable!
    pause
    exit /b 1
)

echo Using Python: %PYTHON_PATH%
echo Working Directory: %cd%
echo.

if not exist "print_server.py" (
    echo ERROR: print_server.py not found
    pause
    exit /b 1
)

REM Install service with NSSM
nssm install BeiZuriPrintServer "%PYTHON_PATH%" "%cd%\print_server.py"
nssm set BeiZuriPrintServer AppDirectory "%cd%"
nssm set BeiZuriPrintServer DisplayName "BeiZuri Print Server"
nssm set BeiZuriPrintServer Description "Thermal printer service for BeiZuri POS system"
nssm set BeiZuriPrintServer Start SERVICE_AUTO_START

REM CRITICAL: Run as LocalSystem to access USB devices
nssm set BeiZuriPrintServer ObjectName LocalSystem

REM Add current directory to PATH so libusb-1.0.dll can be found
nssm set BeiZuriPrintServer AppEnvironmentExtra "PATH=%cd%;%PATH%"

REM Configure logging
nssm set BeiZuriPrintServer AppStdout "%cd%\print_server.log"
nssm set BeiZuriPrintServer AppStderr "%cd%\print_server_error.log"
nssm set BeiZuriPrintServer AppStdoutCreationDisposition 4
nssm set BeiZuriPrintServer AppStderrCreationDisposition 4

REM Configure automatic restart on failure
nssm set BeiZuriPrintServer AppExit Default Restart
nssm set BeiZuriPrintServer AppRestartDelay 5000
nssm set BeiZuriPrintServer AppThrottle 10000

sc failure BeiZuriPrintServer reset= 86400 actions= restart/5000/restart/10000/restart/30000

echo.
echo Starting service...
net start BeiZuriPrintServer

timeout /t 3 /nobreak >nul

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo SUCCESS! Service installed and started!
    echo ========================================
    echo.
    echo Testing printer connection...
    curl http://localhost:8080/status 2>nul
    echo.
    echo.
    echo Service Details:
    echo  - Service Name: BeiZuriPrintServer
    echo  - Status: Running
    echo  - Startup Type: Automatic
    echo  - User: LocalSystem (USB access enabled)
    echo  - Logs: %cd%\print_server.log
    echo.
    echo Test the printer at: http://localhost:8080/test
    echo ========================================
) else (
    echo.
    echo ERROR: Failed to start service!
    echo.
    echo This is likely due to missing USB backend.
    echo Check print_server_error.log for details.
    echo.
    type print_server_error.log 2>nul
    echo.
    echo ========================================
    echo TROUBLESHOOTING:
    echo ========================================
    echo.
    echo If you see "No backend available" error:
    echo.
    echo SOLUTION 1 (Recommended):
    echo   1. Download Zadig from https://zadig.akeo.ie/
    echo   2. Run as Administrator
    echo   3. Options - List All Devices
    echo   4. Select your printer
    echo   5. Install WinUSB driver
    echo   6. Run restart_service.bat
    echo.
    echo SOLUTION 2:
    echo   1. Get libusb-1.0.dll for %PYTHON_ARCH% Python
    echo   2. Place it in: %cd%
    echo   3. Run restart_service.bat
    echo ========================================
    pause
    exit /b 1
)

echo.
echo Creating management scripts...

REM Create restart service script
(
echo @echo off
echo cd /d "%%~dp0"
echo net session ^>nul 2^>^&1
echo if %%errorlevel%% neq 0 ^(
echo     echo Please run as Administrator!
echo     pause
echo     exit /b 1
echo ^)
echo echo Restarting BeiZuri Print Service...
echo net stop BeiZuriPrintServer
echo timeout /t 2 /nobreak ^>nul
echo net start BeiZuriPrintServer
echo echo Service restarted!
echo timeout /t 2 /nobreak ^>nul
echo curl http://localhost:8080/status 2^>nul
echo echo.
echo pause
) > restart_service.bat

REM Create check status script
(
echo @echo off
echo cd /d "%%~dp0"
echo echo ========================================
echo echo BeiZuri Print Server Status
echo echo ========================================
echo sc query BeiZuriPrintServer
echo echo.
echo echo Testing connection...
echo curl http://localhost:8080/status 2^>nul
echo echo.
echo echo.
echo echo Recent Logs:
echo echo ----------------------------------------
echo type print_server.log 2^>nul ^| more
echo echo.
echo pause
) > check_status.bat

REM Create view logs script
(
echo @echo off
echo cd /d "%%~dp0"
echo echo ========================================
echo echo BeiZuri Print Server Logs
echo echo ========================================
echo echo.
echo echo Standard Output:
echo type print_server.log 2^>nul
echo echo.
echo echo ----------------------------------------
echo echo.
echo echo Error Log:
echo type print_server_error.log 2^>nul
echo echo.
echo pause
) > view_logs.bat

REM Create uninstall script
(
echo @echo off
echo cd /d "%%~dp0"
echo net session ^>nul 2^>^&1
echo if %%errorlevel%% neq 0 ^(
echo     echo Please run as Administrator!
echo     pause
echo     exit /b 1
echo ^)
echo echo WARNING: This will uninstall the print service!
echo set /p confirm="Are you sure? (yes/no): "
echo if not "%%confirm%%"=="yes" ^(
echo     echo Uninstall cancelled.
echo     pause
echo     exit /b 0
echo ^)
echo echo Stopping and removing service...
echo net stop BeiZuriPrintServer
echo nssm remove BeiZuriPrintServer confirm
echo echo Service uninstalled!
echo pause
) > uninstall_service.bat

REM Create USB troubleshooting script
(
echo @echo off
echo cd /d "%%~dp0"
echo echo ========================================
echo echo USB Backend Troubleshooting
echo echo ========================================
echo echo.
echo echo Checking for libusb-1.0.dll...
echo if exist "libusb-1.0.dll" ^(
echo     echo ✓ Found: libusb-1.0.dll
echo ^) else ^(
echo     echo ✗ NOT FOUND: libusb-1.0.dll
echo     echo.
echo     echo SOLUTION: Install WinUSB driver with Zadig
echo     echo   1. Download from: https://zadig.akeo.ie/
echo     echo   2. Run as Administrator
echo     echo   3. Options - List All Devices
echo     echo   4. Select your printer
echo     echo   5. Install WinUSB driver
echo ^)
echo echo.
echo echo Checking Python USB library...
echo python -c "import usb.core; print('✓ PyUSB installed')" 2^>nul ^|^| echo ✗ PyUSB not found
echo echo.
echo echo Testing printer detection...
echo python -c "import usb.core; dev = usb.core.find(idVendor=0x0483, idProduct=0x5743); print('✓ Printer found!' if dev else '✗ Printer not found')" 2^>nul
echo echo.
echo echo Service Status:
echo sc query BeiZuriPrintServer ^| findstr "STATE"
echo echo.
echo echo Latest Error Log:
echo echo ----------------------------------------
echo type print_server_error.log 2^>nul ^| findstr /C:"ERROR" /C:"error"
echo echo.
echo pause
) > usb_troubleshoot.bat

echo.
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo Useful Commands:
echo  - restart_service.bat    : Restart the service
echo  - check_status.bat       : Check service status
echo  - view_logs.bat          : View service logs
echo  - usb_troubleshoot.bat   : Diagnose USB issues
echo  - uninstall_service.bat  : Remove service (if needed)
echo.
echo ========================================
echo.
pause