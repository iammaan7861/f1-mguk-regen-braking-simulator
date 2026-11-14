@echo off
cd /d "%~dp0"
echo Rebuilding report and presentation from existing results...
python -c "import sys; sys.path.insert(0, 'builders'); from build_report import build, export_pdf; export_pdf(build())"
if errorlevel 1 goto fail
python -c "import sys; sys.path.insert(0, 'builders'); from build_presentation import build, export_pdf; export_pdf(build())"
if errorlevel 1 goto fail
echo.
echo Wrote Project_Report.docx/.pdf and Presentation.pptx/.pdf
pause
exit /b 0
:fail
echo Build failed. If Word/PowerPoint COM failed, the DOCX/PPTX may still have been written.
pause
exit /b 1
