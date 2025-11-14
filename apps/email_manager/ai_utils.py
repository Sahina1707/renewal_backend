from openai import OpenAI
from django.conf import settings
import json

# Initialize OpenAI client using your .env config
client = OpenAI(
    api_key=settings.OPENAI_API_KEY,
)

def analyze_email_sentiment_and_intent(text: str):
    
    try:
        if not text:
            return {"sentiment": "neutral (50%)", "intent": "unknown"}

        prompt = f"""
        Analyze the following email and provide:
        1. The sentiment (positive, neutral, or negative)
        2. A confidence score (0–100%)
        3. The intent (e.g., renewal_request, complaint, inquiry, gratitude, unsubscribe, confirmation)

        Email:
        {text}

        Respond strictly in JSON format like this:
        {{
            "sentiment": "positive",
            "confidence": 87,
            "intent": "renewal_request"
        }}
        """

        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are an AI email sentiment and intent analyzer."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=int(getattr(settings, "OPENAI_MAX_TOKENS", 150)),
            temperature=float(getattr(settings, "OPENAI_TEMPERATURE", 0.3)),
        )

        content = response.choices[0].message.content.strip()

        # Parse JSON safely
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            result = {"sentiment": "neutral", "confidence": 70, "intent": "unknown"}

        sentiment_label = f"{result.get('sentiment', 'neutral')} ({result.get('confidence', 70)}%)"
        return {
            "sentiment": sentiment_label,
            "intent": result.get("intent", "unknown")
        }

    except Exception as e:
        print(f"⚠️ AI sentiment analysis error: {e}")
        return {"sentiment": "neutral (50%)", "intent": "unknown"}
