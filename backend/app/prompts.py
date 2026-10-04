from typing import Dict, Any

READ_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "label_text": {
            "type": "string",
            "description": "Printed text or numbers on or near the button, or empty string if none"
        },
        "icon_description": {
            "type": "string",
            "description": "Visual shape or icon on the button in at most 6 words, e.g. power symbol, fan blades, clock"
        }
    },
    "required": ["label_text", "icon_description"]
}

EXPLAIN_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "button_name": {
            "type": "string",
            "description": "Name of the button exactly as printed or recognized"
        },
        "what_it_does": {
            "type": "string",
            "description": "One short sentence (under 15 words) saying what the button does"
        },
        "try_this": {
            "type": "string",
            "description": "One short sentence (under 15 words) saying what to press or try"
        },
        "confidence": {
            "type": "string",
            "enum": ["high", "medium", "low"]
        },
        "passages_cover_button": {
            "type": "boolean",
            "description": "True only if the provided manual note explicitly describes this button"
        }
    },
    "required": ["button_name", "what_it_does", "try_this", "confidence", "passages_cover_button"]
}

READ_PROMPT = """You are inspecting a button on a home appliance control panel.
The image is a close-up crop. The button of interest is the single button at the exact center of the image.
Ignore every other button, even if its text is clearer. If the text on the center button is blurry, give your best reading of that word.
Extract:
1. label_text: Any printed text, letters, or numbers directly on or right next to this button (e.g. "FAN", "ECO", "POWER", "TIMER", "ON/OFF"). Copy it exactly. If there is no text, use an empty string.
2. icon_description: Any symbol or icon shape on the button (e.g. power circle with line, fan blades, snowflake, sun, clock).
3. looks_like: A 3 to 5 word description of the button appearance.

Respond strictly in valid JSON using the required schema."""


def build_explain_prompt(
    appliance_name: str,
    appliance_type: str,
    label_text: str,
    icon_description: str,
    user_question: str,
    passages_text: str,
    language: str = "en",
    use_kb: bool = True,
    hindi_strict: bool = False,
    label_note: str = "",
) -> str:
    if language == "hi":
        lang_instruction = (
            "Write what_it_does and try_this ONLY in simple, easy Hindi using Devanagari script. "
            "Do not write them in English. Keep button_name exactly as printed on the appliance."
        )
        if hindi_strict:
            lang_instruction += (
                " IMPORTANT: your previous answer was not fully in Hindi. Every word of "
                "what_it_does and try_this must be Hindi in Devanagari script; Latin letters "
                "are allowed only inside button_name."
            )
    else:
        lang_instruction = "Write all fields in clear, simple English for a non-technical person."

    if use_kb and passages_text.strip():
        kb_instruction = f"""Manual note for this button:
---
{passages_text}
---
Instructions:
- Set passages_cover_button=true ONLY if the note above explicitly describes this button. Otherwise set it to false.
- If passages_cover_button=true, use ONLY the information in the note.
- If passages_cover_button=false, answer briefly from general knowledge and set confidence at most medium."""
    else:
        kb_instruction = """No manual notes are available for this button.
Instructions:
- Set passages_cover_button=false.
- Set confidence at most medium.
"""

    return f"""You are an assistant explaining home appliance buttons to an elderly or non-technical person.
You cannot see the appliance. Rely only on the printed text and icon description below.
Appliance Name: {appliance_name} ({appliance_type})
Button Printed Text: {label_text or "None"}{label_note}
Button Icon Description: {icon_description or "None"}
User Optional Question: {user_question or "What does this button do?"}

{kb_instruction}

General Rules:
- Explain in very simple words a non-technical adult would understand, exactly one short sentence (under 15 words) per field.
- Never invent steps. If the printed text and icon are empty or unclear, say you are not sure and set confidence to low.
- Never say a button starts the appliance unless its printed text says START, ON or POWER. Mode buttons usually need a time set and START pressed afterwards.
- try_this must be one concrete action. Never write "see what happens" or "try it and see"; if you cannot be specific, say you are not sure.
- {lang_instruction}

Respond strictly in valid JSON matching the schema."""
