from typing import Optional, Literal, Any
from langgraph.graph import StateGraph, END
from sqlalchemy.orm import Session

from backend.app.agent.state import PipelineState
from backend.app.agent.nodes import PipelineNodes
from backend.app.llm.client import LLMClient
from backend.app.retrieval.retriever import ScopedRetriever
from backend.app.db.models import Comment, Video, Channel


def should_retrieve_and_draft(state: PipelineState) -> Literal["retrieve", "__end__"]:
    """
    Conditional routing:
    Retrieves and drafts if category matches questions, technical inquiries, or doubts.
    Skips retrieval for complaints, technical corrections, spam, collabs, and praise.
    """
    cat = (state.category or "").strip().lower()
    if any(skip in cat for skip in ("correction", "complaint", "spam", "collab", "praise", "sensitive", "refund")):
        return "__end__"
    if any(k in cat for k in ("question", "inquiry", "doubt", "query", "how", "support")):
        return "retrieve"
    return "__end__"


def build_triage_graph(nodes: PipelineNodes):
    """
    Constructs the LangGraph state machine for Phase 2.
    """
    workflow = StateGraph(PipelineState)

    # Add nodes
    workflow.add_node("classify", nodes.classify_node)
    workflow.add_node("retrieve", nodes.retrieve_node)
    workflow.add_node("draft", nodes.draft_node)

    # Set entry point
    workflow.set_entry_point("classify")

    # Conditional branch after classify
    workflow.add_conditional_edges(
        "classify",
        should_retrieve_and_draft,
        {
            "retrieve": "retrieve",
            "__end__": END,
        },
    )

    # Question workflow sequence: retrieve -> draft -> END
    workflow.add_edge("retrieve", "draft")
    workflow.add_edge("draft", END)

    return workflow.compile()


class TriageAgent:
    """
    High-level runner executing the comment triage graph with grounding & scoping.
    """

    def __init__(self, db: Session, llm_client: LLMClient):
        self.db = db
        self.llm_client = llm_client
        self.retriever = ScopedRetriever(db=db)
        self.nodes = PipelineNodes(llm_client=llm_client, retriever=self.retriever)
        self.graph = build_triage_graph(self.nodes)

    def process_comment(
        self,
        comment: Comment,
        user_preferences: Optional[Any] = None,
    ) -> PipelineState:
        # Resolve tone from user preferences or channel
        tone = "helpful_concise"
        if user_preferences and getattr(user_preferences, "tone", None):
            tone = user_preferences.tone
        elif comment.video and comment.video.channel:
            tone = comment.video.channel.tone_setting or tone

        custom_cats = None
        custom_inst = ""
        if user_preferences:
            if getattr(user_preferences, "categories", None):
                custom_cats = [
                    c.model_dump() if hasattr(c, "model_dump") else c
                    for c in user_preferences.categories
                ]
            custom_inst = getattr(user_preferences, "custom_instructions", "") or ""

        # Resolve active creator persona
        persona_name = None
        persona_instructions = None
        try:
            from backend.app.persona.service import get_active_persona, build_persona_prompt_block
            active_persona = get_active_persona(self.db)
            if active_persona:
                persona_name = active_persona.name
                persona_instructions = build_persona_prompt_block(active_persona, author_name=comment.author or "there")
        except Exception:
            pass

        initial_state = PipelineState(
            comment_id=comment.id,
            youtube_comment_id=comment.youtube_comment_id,
            video_id=comment.video_id,
            comment_text=comment.text,
            author=comment.author,
            channel_tone=tone,
            custom_categories=custom_cats,
            custom_instructions=custom_inst,
            persona_name=persona_name,
            persona_instructions=persona_instructions,
        )

        final_state_dict = self.graph.invoke(initial_state)
        res = PipelineState(**final_state_dict)
        if not res.persona_name and persona_name:
            res.persona_name = persona_name
        return res

