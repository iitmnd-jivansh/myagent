import os
import time
from groq import Groq

SYSTEM_PROMPT = """You are a UI code generator. Your task is to generate complete, self-contained HTML files.

Rules:
1. Output ONLY raw HTML starting with <!DOCTYPE html>
2. Include ALL CSS inline in a <style> tag inside <head>
3. Include ALL JavaScript inline in a <script> tag at the end of <body>
4. Make the UI visually appealing with modern design, colors, and responsive layout
5. Do NOT wrap the output in markdown code blocks (no ```html or ```)
6. Do NOT add any explanation or commentary before or after the HTML
7. The page should be fully functional and self-contained
8. Use a clean, modern design aesthetic with good typography and spacing

Generate a complete, working HTML page based on the user's request."""


def generate_ui(prompt: str) -> str:
    """Generate a complete HTML UI from a natural language prompt using Groq."""
    print("=" * 60)
    print("[CODEGEN] Generating UI from prompt")
    print(f"[CODEGEN]   Prompt: '{prompt}'")
    print("=" * 60)

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("[CODEGEN]   ERROR: GROQ_API_KEY not found in environment")
        return _error_page("GROQ_API_KEY is not configured in .env")

    try:
        client = Groq(api_key=api_key)

        print(f"[CODEGEN]   Calling Groq API (model: llama-3.3-70b-versatile)...")
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=4096,
        )

        html = response.choices[0].message.content.strip()
        print(f"[CODEGEN]   ✅ Response received ({len(html)} chars)")

        # Strip markdown code fences if the LLM ignored instructions
        if html.startswith("```"):
            # Remove opening ```html or ``` and closing ```
            lines = html.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            html = "\n".join(lines).strip()

        # Ensure it starts with DOCTYPE or <html
        if not html.lower().startswith("<!doctype") and not html.lower().startswith("<html"):
            print(f"[CODEGEN]   ⚠️ Response doesn't look like HTML, wrapping in error page")
            html = _error_page(html)

        print(f"[CODEGEN]   ✅ UI generated successfully")
        print(f"[CODEGEN]   HTML length: {len(html)} chars")
        print(f"[CODEGEN]   Preview: {html[:200]}...")
        print("=" * 60)

        return html

    except Exception as e:
        print(f"[CODEGEN]   ❌ Error: {e}")
        print("=" * 60)
        return _error_page(f"Failed to generate UI: {str(e)}")


def _error_page(message: str) -> str:
    """Generate a fallback error page."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Generation Error</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #e0e0e0;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
        }}
        .error-card {{
            background: #16213e;
            border-radius: 16px;
            padding: 40px;
            max-width: 600px;
            text-align: center;
            border: 1px solid #e94560;
        }}
        .error-icon {{ font-size: 48px; margin-bottom: 16px; }}
        h1 {{ color: #e94560; margin-bottom: 12px; font-size: 24px; }}
        p {{ color: #a0a0b0; line-height: 1.6; }}
    </style>
</head>
<body>
    <div class="error-card">
        <div class="error-icon">⚠️</div>
        <h1>UI Generation Error</h1>
        <p>{message}</p>
    </div>
</body>
</html>"""