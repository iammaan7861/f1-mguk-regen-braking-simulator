@echo off
rem Starts the interactive F1 ERS regenerative-braking simulator in your web browser.
cd /d "%~dp0"
echo.
echo  F1 ERS Regenerative Braking Simulator
echo  -------------------------------------
echo  The dashboard opens in your browser at http://localhost:8501
echo  Keep this window open while using it; close it to stop the simulator.
echo.
python -m streamlit run simulator\app.py
if errorlevel 1 (
    echo.
    echo  Could not start. Install the requirements first:
    echo      python -m pip install -r requirements.txt
    pause
)
