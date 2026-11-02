"""Run once on your machine to confirm your Groq key works: python check_ai.py"""
from ai_service import analyze_complaint
from config import get_settings

s = get_settings()
print(f"Provider: {s.base_url}\nModel:    {s.model}\nKey set:  {bool(s.api_key)}")
out = analyze_complaint("No electricity in Hostel Block B since this morning", "Hostel Block B")
print(f"\nMode: {out.mode}   (want: llm)")
print(out.result.model_dump())
if out.warning:
    print("\nWARNING:", out.warning)
