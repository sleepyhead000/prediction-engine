@echo off
echo === Udvash Exam Prediction Engine ===
echo.

echo [1/3] Parsing mhtml files...
python parser.py "."
echo.

echo [2/3] Classifying questions...
python classifier.py parsed_questions.json --no-ai
echo.

echo [3/3] Analyzing patterns...
python analyzer.py classified_questions.json
echo.

echo === Starting Dashboard ===
echo Open http://localhost:8501 in your browser
echo Press Ctrl+C to stop
echo.
streamlit run dashboard.py --server.headless true
