from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class CategoryPreference(BaseModel):
    name: str = Field(..., description="Unique category label (e.g. question, praise, refund_request)")
    description: str = Field(..., description="Guideline for the classifier to match this intent")
    action: Literal["AUTO", "DRAFT", "ESCALATE"] = Field(
        default="DRAFT",
        description="Routing destination for this category",
    )


class UserPreferences(BaseModel):
    categories: List[CategoryPreference] = Field(default_factory=list)
    tone: str = Field(
        default="helpful_concise",
        description="Tone setting for drafted responses (e.g. helpful_concise, formal_professional, warm_friendly, technical_direct)",
    )
    custom_instructions: str = Field(
        default="",
        description="Freeform custom prompt instructions that steer classification and drafting",
    )

    def to_classify_prompt_categories(self) -> str:
        """Formats active categories for inclusion in the classification prompt."""
        if not self.categories:
            return ""
        lines = []
        for idx, cat in enumerate(self.categories, 1):
            lines.append(f'{idx}. "{cat.name.lower()}": {cat.description}')
        return "\n".join(lines)

    def get_action_for_category(self, cat_name: str) -> Optional[str]:
        target = cat_name.strip().lower()
        for cat in self.categories:
            if cat.name.strip().lower() == target:
                return cat.action
        return None


def get_default_preferences() -> UserPreferences:
    """Standard default preferences matching the core YouTube Comment Triage taxonomy."""
    return UserPreferences(
        categories=[
            CategoryPreference(
                name="question",
                description="The user is asking a question about the video content, tutorial, code, tools, or related topic.",
                action="DRAFT",
            ),
            CategoryPreference(
                name="praise",
                description="The user is expressing gratitude, complimenting the video/creator, or leaving positive feedback.",
                action="DRAFT",
            ),
            CategoryPreference(
                name="complaint",
                description="The user is frustrated, reporting video/audio issues, broken links, or expressing dissatisfaction.",
                action="ESCALATE",
            ),
            CategoryPreference(
                name="business_collab",
                description="Inquiries regarding sponsorships, partnerships, promotions, collabs, or business emails.",
                action="ESCALATE",
            ),
            CategoryPreference(
                name="technical_correction",
                description="The user is pointing out a technical bug, code typo, API change, or factual mistake.",
                action="ESCALATE",
            ),
            CategoryPreference(
                name="spam",
                description="Scams, crypto/WhatsApp promotions, telegram links, link farming, self-promotion, or bot comments.",
                action="ESCALATE",
            ),
            CategoryPreference(
                name="sensitive",
                description="Mentions of self-harm, legal threats, severe harassment, hate speech, or safety violations.",
                action="ESCALATE",
            ),
        ],
        tone="helpful_concise",
        custom_instructions="",
    )
