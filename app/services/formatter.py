from typing import Dict, Any, List

def format_snow(summary: Dict[str, Any], qas: List[Dict[str, Any]]) -> str:
    # Remove AI fields from the top table so they don't print as header rows
    ai = summary.pop("ai_summary", None)
    label = summary.pop("ai_label", None)

    lines = []
    lines.append("AI Triage Summary")
    lines.append("-----------------")
    for k, v in summary.items():
        lines.append(f"{k}: {v or '-'}")

    if ai:
        lines.append("")
        if label:
            lines.append(f"AI Label: {label}")
        lines.append("AI Brief:")
        lines.append(ai)

    lines.append("")
    lines.append("Conversation Details:")
    for qa in qas:
        lines.append(f"Q{qa['step']}: {qa['question']}")
        lines.append(f"A{qa['step']}: {qa.get('answer') or '-'}")
    return "\n".join(lines)
