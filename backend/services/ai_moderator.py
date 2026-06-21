import json
import httpx
from typing import Optional
from sqlalchemy.orm import Session
from backend import config, models


def analyze_text_locally(text: str) -> dict:
    """Fallback rule-based text analysis for offline/mock mode."""
    text_lower = text.lower()
    
    # 1. Simple Spam check
    spam_triggers = ["buy bitcoin", "get rich fast", "make money online", "viagra", "scam", "click here to win"]
    is_spam = any(trigger in text_lower for trigger in spam_triggers)
    if is_spam:
        return {
            "is_flagged": True,
            "category": "SPAM",
            "score": 0.9,
            "explanation": "Contains known financial/spam trigger keywords."
        }
        
    # 2. Simple Abuse check
    abusive_triggers = ["idiot", "hate you", "kill yourself", "bastard", "fuck"]
    is_abuse = any(trigger in text_lower for trigger in abusive_triggers)
    if is_abuse:
        return {
            "is_flagged": True,
            "category": "ABUSE",
            "score": 0.85,
            "explanation": "Contains hostile or abusive language."
        }
        
    return {
        "is_flagged": False,
        "category": "NONE",
        "score": 0.0,
        "explanation": "No issues detected."
    }

async def analyze_text_gemini(text: str) -> dict:
    """Calls Google Gemini API to analyze and flag message content."""
    api_key = config.GEMINI_API_KEY
    if not api_key:
        return analyze_text_locally(text)
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    system_instruction = (
        "You are an AI community moderator. Analyze the user text for SPAM, ABUSE, HATE_SPEECH, or EMERGENCY. "
        "Return ONLY a JSON object with this structure: "
        '{"is_flagged": true/false, "category": "SPAM"|"ABUSE"|"HATE_SPEECH"|"EMERGENCY"|"NONE", "score": float_between_0_and_1, "explanation": "string"}. '
        "Do not include markdown blocks or any other characters."
    )
    
    payload = {
        "contents": [
            {"parts": [{"text": f"System context:\n{system_instruction}\n\nAnalyze this message: '{text}'"}]}
        ],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(url, json=payload, timeout=8.0)
            if res.status_code == 200:
                data = res.json()
                text_content = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                parsed = json.loads(text_content)
                return parsed
            else:
                print(f"[GEMINI API WARNING] API returned status {res.status_code}. Using local fallback.")
                return analyze_text_locally(text)
    except Exception as e:
        print(f"[GEMINI API ERROR] {e}. Using local fallback.")
        return analyze_text_locally(text)

async def audit_user_message(db: Session, user_id: str, location_id: Optional[int], text: str) -> bool:
    """
    Audits a message sent by a citizen. Logs flagged items and auto-mutes high-confidence violations.
    Returns True if the message was flagged.
    """
    if config.AI_PROVIDER == "gemini":
        analysis = await analyze_text_gemini(text)
    else:
        analysis = analyze_text_locally(text)

    if analysis.get("is_flagged", False):
        print(f"[AI MODERATOR FLAGGED] category={analysis.get('category')} score={analysis.get('score')} text='{text}'")
        
        # Log to Database
        log = models.ModerationLog(
            location_id=location_id,
            user_id=user_id,
            message_text=text,
            ai_analysis=analysis
        )
        db.add(log)
        
        # Auto-mute if threat score is extremely high (e.g. > 0.85)
        if analysis.get("score", 0.0) >= 0.85:
            user = db.query(models.User).filter(models.User.id == user_id).first()
            if user:
                user.is_muted = True
                print(f"[AI AUTO-ACTION] Auto-muted user {user.username} due to high confidence violation.")
                
        db.commit()
        return True

    return False
