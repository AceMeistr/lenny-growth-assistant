import os
import re

def extract():
    dest_dir = os.path.join(os.getcwd(), "agent_transcripts")
    os.makedirs(dest_dir, exist_ok=True)

    src_log = r"C:\Users\sasan\.gemini\antigravity-ide\brain\c6947fc4-4de2-47f5-a9a3-fa9e165638e1\.system_generated\logs\transcript.jsonl"
    dest_jsonl = os.path.join(dest_dir, "session_transcript.jsonl")

    if os.path.exists(src_log):
        count = 0
        with open(src_log, "r", encoding="utf-8", errors="ignore") as f_in, open(dest_jsonl, "w", encoding="utf-8") as f_out:
            for line in f_in:
                cleaned = re.sub(r"sk-ant-[a-zA-Z0-9_\-]+", "[REDACTED_KEY]", line)
                cleaned = re.sub(r'anthropic_api_key":\s*"[^"]+"', 'anthropic_api_key": "[REDACTED]"', cleaned)
                f_out.write(cleaned)
                count += 1
        print(f"Sanitized and copied {count} transcript lines to {dest_jsonl}")
    else:
        print("Source transcript not found at", src_log)

if __name__ == "__main__":
    extract()
