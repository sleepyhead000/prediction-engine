@echo off
echo Installing prediction-engine dependencies...
pip install lxml pydantic requests httpx PyMuPDF selectolax chromadb sentence-transformers scikit-learn rapidfuzz pytest ruff
echo.
echo Done. Run: pip install -e .
