@echo off
REM Quick test script for FMU Gateway
echo ======================================================================
echo FMU GATEWAY - SIMULATION TEST
echo ======================================================================
echo.

REM Navigate to project directory
cd /d "%~dp0"

echo Running auto-detection simulation test...
echo.

python run_fmu_simulation.py --auto --fmu=app/library/msl/BouncingBall.fmu

echo.
echo ======================================================================
echo Test complete! Check the results above.
echo ======================================================================
pause

