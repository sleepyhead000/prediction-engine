"""Analyze classified questions: frequency, temporal patterns, predictions."""
import json
import os
from collections import defaultdict, Counter
from pathlib import Path


def analyze_all(data: list[dict]) -> dict:
    """Run full analysis on classified question data."""
    # Topic frequency by subject
    topic_freq = defaultdict(lambda: defaultdict(int))
    # Topic frequency by exam type
    topic_by_type = defaultdict(lambda: defaultdict(int))
    # Questions per file
    questions_per_file = []
    # All questions flat list
    all_questions = []

    for file_data in data:
        subject = file_data.get("subject", "Unknown")
        exam_type = file_data.get("exam_type", "Unknown")
        set_num = file_data.get("set_number", 0)
        fname = os.path.basename(file_data.get("file", ""))

        questions_per_file.append({
            "file": fname,
            "subject": subject,
            "exam_type": exam_type,
            "set_number": set_num,
            "count": file_data.get("question_count", 0),
        })

        for q in file_data.get("questions", []):
            topic = q.get("topic", "Unknown")
            topic_freq[subject][topic] += 1
            topic_by_type[exam_type][topic] += 1
            q["source_file"] = fname
            q["exam_type"] = exam_type
            q["set_number"] = set_num
            all_questions.append(q)

    # Temporal analysis: daily → weekly patterns
    temporal = analyze_temporal(data)

    # Predictions: what's likely to appear next
    predictions = generate_predictions(topic_freq, temporal, all_questions)

    return {
        "topic_frequency": dict(topic_freq),
        "topic_by_type": dict(topic_by_type),
        "questions_per_file": questions_per_file,
        "total_questions": len(all_questions),
        "temporal_analysis": temporal,
        "predictions": predictions,
        "topic_summary": build_topic_summary(topic_freq),
    }


def analyze_temporal(data: list[dict]) -> dict:
    """Analyze daily → weekly temporal patterns."""
    daily_topics = defaultdict(lambda: defaultdict(int))
    weekly_topics = defaultdict(lambda: defaultdict(int))

    for file_data in data:
        exam_type = file_data.get("exam_type", "Unknown")
        subject = file_data.get("subject", "Unknown")
        set_num = file_data.get("set_number", 0)

        for q in file_data.get("questions", []):
            topic = q.get("topic", "Unknown")
            if exam_type in ("MCQ", "Written"):
                daily_topics[f"{subject}_Set{set_num}"][topic] += 1
            elif exam_type == "Weekly":
                weekly_topics[f"Weekly_Set{set_num}"][topic] += 1

    # Check overlap: which daily topics appear in weekly
    topic_overlap = defaultdict(lambda: {"daily_count": 0, "weekly_count": 0, "overlap": 0})

    for day_key, day_topics in daily_topics.items():
        for topic, count in day_topics.items():
            topic_overlap[topic]["daily_count"] += count

    for week_key, week_topics in weekly_topics.items():
        for topic, count in week_topics.items():
            topic_overlap[topic]["weekly_count"] += count
            if topic in topic_overlap:
                topic_overlap[topic]["overlap"] += min(count, topic_overlap[topic]["daily_count"])

    return {
        "daily_topics": dict(daily_topics),
        "weekly_topics": dict(weekly_topics),
        "topic_overlap": dict(topic_overlap),
    }


def generate_predictions(topic_freq: dict, temporal: dict, all_questions: list[dict]) -> dict:
    """Generate predictions for next exam."""
    predictions = {}

    for subject, topics in topic_freq.items():
        total = sum(topics.values())
        if total == 0:
            continue

        # Base prediction: frequency score
        subject_predictions = []
        for topic, count in topics.items():
            freq_score = count / total * 100

            # Temporal boost: topics that appear in daily and weekly get a boost
            overlap = temporal.get("topic_overlap", {}).get(topic, {})
            daily_count = overlap.get("daily_count", 0)
            weekly_count = overlap.get("weekly_count", 0)

            # Boost for topics that appear in both daily and weekly
            temporal_boost = 0
            if daily_count > 0 and weekly_count > 0:
                temporal_boost = min(weekly_count / daily_count * 10, 15)

            # Recency boost: topics in more recent sets get higher score
            recency_score = 0
            recent_questions = [q for q in all_questions
                              if q.get("subject") == subject and q.get("topic") == topic]
            if recent_questions:
                max_set = max(q.get("set_number", 0) for q in recent_questions)
                recency_score = max_set * 2

            # Combined score
            confidence = min(freq_score + temporal_boost + recency_score, 95)

            subject_predictions.append({
                "topic": topic,
                "frequency_count": count,
                "frequency_pct": round(freq_score, 1),
                "temporal_boost": round(temporal_boost, 1),
                "recency_score": round(recency_score, 1),
                "confidence": round(confidence, 1),
            })

        # Sort by confidence
        subject_predictions.sort(key=lambda x: x["confidence"], reverse=True)
        predictions[subject] = subject_predictions

    return predictions


def build_topic_summary(topic_freq: dict) -> list[dict]:
    """Build a flat summary of all topics across subjects."""
    summary = []
    for subject, topics in topic_freq.items():
        total = sum(topics.values())
        for topic, count in topics.items():
            summary.append({
                "subject": subject,
                "topic": topic,
                "count": count,
                "percentage": round(count / total * 100, 1) if total > 0 else 0,
            })
    summary.sort(key=lambda x: x["count"], reverse=True)
    return summary


def get_heatmap_data(data: list[dict]) -> dict:
    """Generate heatmap data for visualization."""
    # Heatmap: rows = topics, columns = exam sets
    heatmap = {}

    for file_data in data:
        subject = file_data.get("subject", "Unknown")
        exam_type = file_data.get("exam_type", "Unknown")
        set_num = file_data.get("set_number", 0)
        label = f"{exam_type} {set_num}"

        if subject not in heatmap:
            heatmap[subject] = {"labels": [], "topics": defaultdict(list)}

        for q in file_data.get("questions", []):
            topic = q.get("topic", "Unknown")
            if topic not in heatmap[subject]["topics"]:
                heatmap[subject]["topics"][topic] = []
            # Count questions per topic per set
            topic_count = sum(1 for qq in file_data.get("questions", []) if qq.get("topic") == topic)
            heatmap[subject]["topics"][topic].append({"set": label, "count": topic_count})

    return heatmap


if __name__ == "__main__":
    import sys

    input_file = sys.argv[1] if len(sys.argv) > 1 else "classified_questions.json"

    print(f"Loading classified questions from: {input_file}")
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = analyze_all(data)

    output_file = "analysis_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Saved to: {output_file}")

    # Print summary
    print("\n=== Topic Summary ===")
    for item in results["topic_summary"][:15]:
        print(f"  {item['subject']:10s} | {item['topic'][:40]:40s} | {item['count']:3d} ({item['percentage']:.1f}%)")

    print("\n=== Predictions for Next Exam ===")
    for subject, preds in results["predictions"].items():
        print(f"\n{subject}:")
        for p in preds[:5]:
            print(f"  {p['topic'][:45]:45s} | conf: {p['confidence']:.1f}% | freq: {p['frequency_pct']:.1f}%")
