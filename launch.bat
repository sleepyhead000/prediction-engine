@echo off
title Udvash Exam Prediction Engine
color 0A

echo ============================================
echo    Udvash Exam Prediction Engine
============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ and add to PATH.
    pause
    exit /b 1
)

:: Check dependencies
echo [0/5] Checking dependencies...
python -c "import bs4, streamlit, requests, pandas, pymupdf" >nul 2>&1
if errorlevel 1 (
    echo [!] Installing dependencies...
    pip install beautifulsoup4 streamlit requests pandas PyMuPDF --quiet
)

:: Start LocalAPI proxy for AI classification
echo [1/5] Starting LocalAPI proxy...
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo [!] LocalAPI not running — starting it...
    start /min "" python "%~dp0LocalAPI\server.py"
    timeout /t 3 /nobreak >nul
    curl -s http://localhost:8000/health >nul 2>&1
    if errorlevel 1 (
        echo [WARNING] LocalAPI failed to start — using keyword classification
        set USE_AI=--no-ai
    ) else (
        echo [+] LocalAPI started on port 8000
        set USE_AI=
    )
) else (
    echo [+] LocalAPI already running
    set USE_AI=
)
echo.

:: Parse
echo [2/5] Parsing mhtml + PDF files...
python parser.py "."
if errorlevel 1 (
    echo [ERROR] Parser failed.
    pause
    exit /b 1
)
echo.

:: Classify
echo [3/5] Classifying questions into topics...
python classifier.py parsed_questions.json %USE_AI%
if errorlevel 1 (
    echo [ERROR] Classifier failed.
    pause
    exit /b 1
)
echo.

:: Analyze
echo [4/5] Analyzing patterns and generating predictions...
python analyzer.py classified_questions.json
if errorlevel 1 (
    echo [ERROR] Analyzer failed.
    pause
    exit /b 1
)
echo.

:: Launch dashboard
echo [5/5] Launching dashboard...
echo.
echo ============================================
echo    Dashboard: http://localhost:8501
echo    Press Ctrl+C to stop
echo ============================================
echo.
streamlit run dashboard.py --server.headless true --browser.gatherUsageStats false
