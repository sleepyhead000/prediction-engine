"""Streamlit dashboard for Udvash Exam Prediction Engine."""
import json
import os
import sys

import pandas as pd
import streamlit as st

# Add current dir to path for imports
sys.path.insert(0, os.path.dirname(__file__))
from parser import parse_all_exams, save_parsed
from classifier import classify_all_questions
from analyzer import analyze_all, get_heatmap_data

# Page config
st.set_page_config(
    page_title="Udvash Exam Predictor",
    page_icon="",
    layout="wide",
)

st.title("Udvash Exam Prediction Engine")
st.caption("Analyze past exams and predict what's coming next")

# Sidebar
st.sidebar.header("Controls")
data_dir = st.sidebar.text_input("Exam Data Directory", value=".")

# Auto-detect LocalAI
localai_ok = False
try:
    import requests
    r = requests.get("http://localhost:8000/health", timeout=2)
    localai_ok = r.status_code == 200
except Exception:
    pass

if localai_ok:
    use_ai = st.sidebar.checkbox("Use AI Classification", value=True)
    st.sidebar.success("LocalAI detected")
else:
    use_ai = False
    st.sidebar.warning("LocalAI not found — keyword only")
run_button = st.sidebar.button("Analyze Exams", type="primary")

if run_button:
    with st.spinner("Parsing mhtml + PDF files..."):
        parsed = parse_all_exams(data_dir)
        total_q = sum(f.get("question_count", 0) for f in parsed)
        st.sidebar.success(f"Parsed {len(parsed)} files, {total_q} questions")

    with st.spinner("Classifying questions into topics..."):
        classified = classify_all_questions(parsed, use_ai=use_ai)
        # Save intermediate
        with open("classified_questions.json", "w", encoding="utf-8") as f:
            json.dump(classified, f, ensure_ascii=False, indent=2)

    with st.spinner("Analyzing patterns..."):
        results = analyze_all(classified)

    st.session_state["results"] = results
    st.session_state["classified"] = classified
    st.sidebar.success("Analysis complete!")

# Main content
# Auto-load pre-computed results if available
if "results" not in st.session_state:
    try:
        with open("analysis_results.json", "r", encoding="utf-8") as f:
            st.session_state["results"] = json.load(f)
        with open("classified_questions.json", "r", encoding="utf-8") as f:
            st.session_state["classified"] = json.load(f)
    except FileNotFoundError:
        pass

if "results" in st.session_state:
    results = st.session_state["results"]
    classified = st.session_state["classified"]

    # Summary stats
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Questions", results["total_questions"])
    col2.metric("Subjects", len(results["topic_frequency"]))
    col3.metric("Unique Topics", len(results["topic_summary"]))
    col4.metric("Exam Files", len(results["questions_per_file"]))

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["Predictions", "Heatmap", "Topic Details", "Raw Data"])

    with tab1:
        st.header("Predictions for Next Exam")
        for subject, preds in results["predictions"].items():
            st.subheader(subject)
            df = pd.DataFrame(preds)
            # Color code confidence
            def color_confidence(val):
                if val >= 70:
                    return "background-color: #ff6b6b"
                elif val >= 50:
                    return "background-color: #ffd93d"
                else:
                    return "background-color: #6bcb77"

            st.dataframe(
                df.style.map(color_confidence, subset=["confidence"]),
                column_config={
                    "topic": "Topic",
                    "frequency_count": "Count",
                    "frequency_pct": st.column_config.NumberColumn("Frequency %", format="%.1f%%"),
                    "temporal_boost": st.column_config.NumberColumn("Temporal Boost", format="%.1f"),
                    "confidence": st.column_config.NumberColumn("Confidence %", format="%.1f%%"),
                },
                hide_index=True,
                use_container_width=True,
            )

    with tab2:
        st.header("Topic Frequency Heatmap")
        for subject in results["topic_frequency"]:
            st.subheader(subject)
            topics = results["topic_frequency"][subject]
            if topics:
                df_heat = pd.DataFrame(
                    list(topics.items()),
                    columns=["Topic", "Count"]
                ).sort_values("Count", ascending=False)
                st.bar_chart(df_heat.set_index("Topic"))

    with tab3:
        st.header("Topic Details")
        for subject, topics in results["topic_frequency"].items():
            st.subheader(subject)
            total = sum(topics.values())
            for topic, count in sorted(topics.items(), key=lambda x: -x[1]):
                pct = count / total * 100 if total > 0 else 0
                st.write(f"**{topic}**: {count} questions ({pct:.1f}%)")

    with tab4:
        st.header("Raw Question Data")
        # Flatten for display
        all_qs = []
        for file_data in classified:
            for q in file_data.get("questions", []):
                all_qs.append({
                    "Subject": q.get("subject", ""),
                    "Topic": q.get("topic", ""),
                    "Exam Type": q.get("exam_type", ""),
                    "Set": q.get("set_number", ""),
                    "Q#": q.get("question_number", ""),
                    "Text": q.get("question_text", "")[:100],
                    "Source": "PDF" if q.get("source_file", "").endswith(".pdf") else "Mhtml",
                })
        if all_qs:
            st.dataframe(pd.DataFrame(all_qs), use_container_width=True)

else:
    st.info("👈 Set your exam data directory and click **Analyze Exams** to start.")

    # Show project structure
    st.markdown("---")
    st.markdown("### How to use")
    st.markdown("""
    1. Place your exam files (mhtml + PDF) in the data directory
    2. Click **Analyze Exams** in the sidebar
    3. View predictions, heatmap, and topic breakdowns

    **Supported file types:**
    - `.mhtml` — saved web pages from Udvash online portal
    - `.pdf` — question banks, diff sets (AI reads image-based PDFs via LocalAI)

    **File structure:**
    ```
    exam-data/
    ├── Physics/
    │   ├── P1 MCQ 1.mhtml
    │   ├── Physics2.pdf
    │   └── ...
    ├── Chemistry/
    ├── Math/
    │   └── math2.pdf
    ├── Weekly 1/
    ├── WEEK 2 DAILYS/
    └── Question Bank/
    ```
    """)
