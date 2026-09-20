@echo off
title OCR - Board Book Scanner
echo ============================================
echo   prediction-engine OCR (Intel Arc A580)
echo ============================================
echo.

set VENV=G:\prediction-engine\.venv\Scripts
set PYTHON=%VENV%\python.exe

set HF_HOME=G:\prediction-engine\cache\huggingface
set EASYOCR_MODEL_PATH=G:\prediction-engine\cache\easyocr

echo Device check:
%PYTHON% -c "import torch; print(f'  torch={torch.__version__}, xpu={torch.xpu.is_available()}')"
echo.

echo Starting OCR...
echo   Source:  sources\books
echo   Output:  data\book_pages.jsonl
echo   GPU:     ON (XPU)
echo.

%PYTHON% -m scripts.ocr_books --gpu --src sources/books --out data/book_pages.jsonl

echo.
echo ============================================
echo   Done!
echo ============================================
pause
