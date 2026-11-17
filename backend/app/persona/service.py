import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from backend.app.db.models import CreatorPersona, Reply, Comment
from backend.app.core.logging import logger

DEFAULT_PERSONAS = [
    {
        "name": "Default / Balanced",
        "description": "Clean, conversational, and direct with light warmth and exact timestamp citations.",
        "is_active": True,
        "greeting_pattern": "Hey @author!",
        "sign_off_pattern": "None",
        "formality": "neutral",
        "emoji_density": "minimal",
        "max_sentences": 2,
        "custom_voice_notes": "Be clear, concise, and helpful. Always cite the exact timestamp when answering technical questions.",
        "sample_pairs": [
            {
                "comment": "Where do we install Docker on Windows?",
                "reply": "Hey @author! You can download Docker Desktop directly from docker.com, as shown around [02:15].",
            },
            {
                "comment": "Does this work with Python 3.12?",
                "reply": "Hey @author! Yes, Python 3.10 through 3.12 are fully supported as demonstrated at [04:40].",
            },
        ],
    },
    {
        "name": "Friendly Mentor",
        "description": "Warm, encouraging, beginner-friendly tone with supportive emojis and upbeat sign-off.",
        "is_active": False,
        "greeting_pattern": "Hi @author!",
        "sign_off_pattern": "Hope this helps! 🚀",
        "formality": "casual",
        "emoji_density": "expressive",
        "max_sentences": 3,
        "custom_voice_notes": "Encouraging, warm, and uplifting tone. Validate the user's question and guide them with enthusiasm.",
        "sample_pairs": [
            {
                "comment": "I got a KeyError on line 42 when running the ingestion script.",
                "reply": "Hi @author! Don't worry, that happens when the dictionary key isn't initialized yet—check out [06:30] for the exact fix! Hope this helps! 🚀",
            },
            {
                "comment": "Can I use this for my final year computer science project?",
                "reply": "Hi @author! Absolutely, this makes a fantastic portfolio project! We walk through the architecture overview at [01:10]. Hope this helps! 🚀",
            },
        ],
    },
    {
        "name": "Technical & Direct",
        "description": "Zero conversational filler, highly factual, precise engineering documentation tone.",
        "is_active": False,
        "greeting_pattern": "None",
        "sign_off_pattern": "None",
        "formality": "formal",
        "emoji_density": "none",
        "max_sentences": 2,
        "custom_voice_notes": "Direct answers with zero conversational filler. State the exact solution and timestamp citation immediately.",
        "sample_pairs": [
            {
                "comment": "What port does the FastAPI server listen on?",
                "reply": "The FastAPI backend server binds to port 8000 by default ([01:10]).",
            },
            {
                "comment": "Which embedding model is used for local retrieval?",
                "reply": "Local embeddings use sentence-transformers/all-MiniLM-L6-v2 running on CPU ([03:25]).",
            },
        ],
    },
]


def seed_default_personas(db: Session) -> List[CreatorPersona]:
    """Seeds default creator personas if the table is currently empty."""
    existing_count = db.query(CreatorPersona).count()
    if existing_count > 0:
        return db.query(CreatorPersona).order_by(CreatorPersona.id.asc()).all()

    created_personas = []
    for p_data in DEFAULT_PERSONAS:
        persona = CreatorPersona(
            name=p_data["name"],
            description=p_data["description"],
            is_active=p_data["is_active"],
            greeting_pattern=p_data["greeting_pattern"],
            sign_off_pattern=p_data["sign_off_pattern"],
            formality=p_data["formality"],
            emoji_density=p_data["emoji_density"],
            max_sentences=p_data["max_sentences"],
            custom_voice_notes=p_data["custom_voice_notes"],
            sample_pairs=p_data["sample_pairs"],
        )
        db.add(persona)
        created_personas.append(persona)

    db.commit()
    for cp in created_personas:
        db.refresh(cp)
    logger.info(f"Seeded {len(created_personas)} default creator personas into database.")
    return created_personas


def get_active_persona(db: Session) -> Optional[CreatorPersona]:
    """Retrieves the currently active persona, seeding defaults if needed."""
    active = db.query(CreatorPersona).filter(CreatorPersona.is_active.is_(True)).first()
    if active:
        return active

    personas = seed_default_personas(db)
    if personas:
        personas[0].is_active = True
        db.commit()
        db.refresh(personas[0])
        return personas[0]
    return None


def set_active_persona(db: Session, persona_id: int) -> Optional[CreatorPersona]:
    """Activates the specified persona and deactivates all others."""
    persona = db.query(CreatorPersona).filter(CreatorPersona.id == persona_id).first()
    if not persona:
        return None

    # Deactivate all
    db.query(CreatorPersona).update({CreatorPersona.is_active: False})
    persona.is_active = True
    db.commit()
    db.refresh(persona)
    logger.info(f"Activated persona id={persona.id} ('{persona.name}')")
    return persona


# Regex patterns for tone extraction
EMOJI_PATTERN = re.compile(
    r"[\U0001F600-\U0001F64F"  # emoticons
    r"\U0001F300-\U0001F5FF"  # symbols & pictographs
    r"\U0001F680-\U0001F6FF"  # transport & map
    r"\U0001F1E0-\U0001F1FF"  # flags
    r"\U00002702-\U000027B0"
    r"\U000024C2-\U0001F251"
    r"]+",
    flags=re.UNICODE,
)

GREETING_REGEXES = [
    (re.compile(r"^(hey\s+@?author|hey\s+there|hey\b)", re.IGNORECASE), "Hey @author!"),
    (re.compile(r"^(hi\s+@?author|hi\s+there|hi\b)", re.IGNORECASE), "Hi @author!"),
    (re.compile(r"^(hello\s+@?author|hello\b)", re.IGNORECASE), "Hello @author,"),
    (re.compile(r"^(yo\b|what\'s\s+up)", re.IGNORECASE), "Yo @author!"),
]

SIGN_OFF_REGEXES = [
    (re.compile(r"(hope\s+this\s+helps[!.]?\s*(🚀|😊)?)$", re.IGNORECASE), "Hope this helps! 🚀"),
    (re.compile(r"(cheers[!.]?\s*([a-zA-Z]+)?)$", re.IGNORECASE), "Cheers!"),
    (re.compile(r"(best,\s*([a-zA-Z]+)?)$", re.IGNORECASE), "Best,"),
    (re.compile(r"(-\s*[a-zA-Z]+)$", re.IGNORECASE), "- Creator"),
]


def extract_tone_from_texts(texts: List[str]) -> Dict[str, Any]:
    """
    Analyzes a collection of creator replies to extract their stylistic DNA:
    greeting patterns, sign-off signatures, emoji density, sentence brevity, and formality.
    """
    clean_texts = [t.strip() for t in texts if t and t.strip()]
    if not clean_texts:
        return {
            "name": "Cloned Voice",
            "description": "Auto-extracted creator voice profile",
            "greeting_pattern": "Hey @author!",
            "sign_off_pattern": "None",
            "formality": "neutral",
            "emoji_density": "minimal",
            "max_sentences": 2,
            "custom_voice_notes": "Answer grounded in video timestamps with concise sentence flow.",
            "sample_count": 0,
            "metrics": {
                "avg_sentence_count": 2.0,
                "emoji_ratio": 0.2,
                "has_greeting_ratio": 0.5,
                "has_sign_off_ratio": 0.2,
            },
        }

    total_texts = len(clean_texts)
    sentence_counts = []
    emoji_counts = []
    detected_greetings = []
    detected_sign_offs = []

    casual_markers = {"gonna", "wanna", "lol", "awesome", "cool", "super", "rock", "hey", "check out"}
    formal_markers = {"therefore", "however", "additionally", "demonstrates", "refer to", "specifically"}
    casual_score = 0
    formal_score = 0

    for text in clean_texts:
        # Sentence splitting (strip emojis first to avoid trailing fragments)
        cleaned_for_sentences = EMOJI_PATTERN.sub("", text).strip()
        sentences = [s.strip() for s in re.split(r"[.!?]+", cleaned_for_sentences) if len(s.strip()) > 2]
        sentence_counts.append(max(1, len(sentences)))

        # Emojis
        emojis_found = EMOJI_PATTERN.findall(text)
        emoji_counts.append(len(emojis_found))

        # Greetings
        matched_greeting = None
        for pattern, template in GREETING_REGEXES:
            if pattern.search(text):
                matched_greeting = template
                break
        if matched_greeting:
            detected_greetings.append(matched_greeting)

        # Sign-offs
        matched_sign_off = None
        for pattern, template in SIGN_OFF_REGEXES:
            if pattern.search(text):
                matched_sign_off = template
                break
        if matched_sign_off:
            detected_sign_offs.append(matched_sign_off)

        # Formality analysis
        lower = text.lower()
        casual_score += sum(1 for m in casual_markers if m in lower)
        formal_score += sum(1 for m in formal_markers if m in lower)
        if "!" in text:
            casual_score += text.count("!")

    # Averages
    avg_sentences = round(sum(sentence_counts) / total_texts, 1)
    max_sentences = max(1, min(4, round(avg_sentences)))
    avg_emojis = sum(emoji_counts) / total_texts

    # Emoji density
    if avg_emojis == 0:
        emoji_density = "none"
    elif avg_emojis <= 1.0:
        emoji_density = "minimal"
    else:
        emoji_density = "expressive"

    # Greeting pattern
    if detected_greetings and len(detected_greetings) / total_texts >= 0.35:
        # Pick the most frequent
        greeting_pattern = max(set(detected_greetings), key=detected_greetings.count)
    else:
        greeting_pattern = "None"

    # Sign off pattern
    if detected_sign_offs and len(detected_sign_offs) / total_texts >= 0.25:
        sign_off_pattern = max(set(detected_sign_offs), key=detected_sign_offs.count)
    else:
        sign_off_pattern = "None"

    # Formality level
    if casual_score > formal_score * 1.5 or "!" in "".join(clean_texts):
        formality = "casual"
    elif formal_score > casual_score:
        formality = "formal"
    else:
        formality = "neutral"

    # Voice description
    desc = f"Auto-cloned from {total_texts} sample replies: {formality} tone, {emoji_density} emojis, ~{max_sentences} sentences max."

    return {
        "name": "My Cloned Persona",
        "description": desc,
        "greeting_pattern": greeting_pattern,
        "sign_off_pattern": sign_off_pattern,
        "formality": formality,
        "emoji_density": emoji_density,
        "max_sentences": max_sentences,
        "custom_voice_notes": f"Adopt creator's natural {formality} style with {emoji_density} emojis. Keep responses tightly grounded under {max_sentences} sentences.",
        "sample_count": total_texts,
        "metrics": {
            "avg_sentence_count": avg_sentences,
            "emoji_ratio": round(avg_emojis, 2),
            "has_greeting_ratio": round(len(detected_greetings) / total_texts, 2),
            "has_sign_off_ratio": round(len(detected_sign_offs) / total_texts, 2),
        },
    }


def extract_tone_from_approved_db(db: Session) -> Dict[str, Any]:
    """Extracts tone profile automatically from all comments in the DB with approved replies."""
    # Find replies that are finalized or marked published/approved
    replies = (
        db.query(Reply)
        .filter(Reply.final_text != "")
        .limit(50)
        .all()
    )
    texts = [r.final_text for r in replies if r.final_text.strip()]
    if not texts:
        # Fallback to draft_text if final_text is empty
        replies_draft = db.query(Reply).filter(Reply.draft_text != "").limit(50).all()
        texts = [r.draft_text for r in replies_draft if r.draft_text.strip()]

    result = extract_tone_from_texts(texts)
    result["name"] = "Channel Historical Voice"
    result["description"] = f"Learned from {len(texts)} historical replies in CommentIQ."
    return result


def build_persona_prompt_block(persona: Optional[CreatorPersona], author_name: str = "there") -> str:
    """
    Constructs the stylistic instructions and few-shot examples to inject into the Drafter prompt.
    Keeps factual grounding strictly intact while styling voice and formatting.
    """
    if not persona:
        return ""

    blocks = ["\nCREATOR PERSONA & VOICE STYLING:"]
    blocks.append(f"- Active Persona: {persona.name}")
    blocks.append(f"- Formality Level: {persona.formality.capitalize()}")

    # Greeting instruction
    if persona.greeting_pattern and persona.greeting_pattern.lower() != "none":
        greeting_text = persona.greeting_pattern.replace("@author", f"@{author_name}").replace("{author}", author_name)
        blocks.append(f"- Greeting Rule: Open the reply with a natural greeting like '{greeting_text}'")
    else:
        blocks.append("- Greeting Rule: Do NOT include any greeting. Start directly with the answer.")

    # Sign-off instruction
    if persona.sign_off_pattern and persona.sign_off_pattern.lower() != "none":
        blocks.append(f"- Sign-off Rule: End the reply with a warm closing like '{persona.sign_off_pattern}'")
    else:
        blocks.append("- Sign-off Rule: Do NOT include any sign-off signature.")

    # Emoji density
    if persona.emoji_density == "none":
        blocks.append("- Emoji Usage: Do NOT use any emojis.")
    elif persona.emoji_density == "minimal":
        blocks.append("- Emoji Usage: Use at most 1 subtle, relevant emoji if appropriate.")
    elif persona.emoji_density == "expressive":
        blocks.append("- Emoji Usage: Use 1-2 friendly, expressive emojis (e.g. 🚀, ✨, 👍).")

    # Max sentences
    blocks.append(f"- Brevity Limit: Keep the entire reply within {persona.max_sentences} sentences maximum.")

    if persona.custom_voice_notes:
        blocks.append(f"- Creator Notes: {persona.custom_voice_notes}")

    # Dynamic Few-Shot Examples
    if persona.sample_pairs and isinstance(persona.sample_pairs, list):
        blocks.append("\nFEW-SHOT VOICE EXAMPLES (Match this style and tone):")
        for i, pair in enumerate(persona.sample_pairs[:3]):
            q = pair.get("comment", "")
            a = pair.get("reply", "")
            if q and a:
                blocks.append(f"Example {i+1}:\nUser: \"{q}\"\nCreator Reply: \"{a}\"")

    return "\n".join(blocks)
