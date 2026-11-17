# YouTube Comment Triage Benchmark: Labeling Guide

This labeling guide defines the ground truth taxonomy and annotation rules for evaluating the YouTube Comment Triage Agent across 100 benchmark comments.

---

## 1. Primary Taxonomy (7 Categories)

| Category | Description | Primary Indicators | Ground Truth Expected Action |
| :--- | :--- | :--- | :--- |
| **`question`** | Genuine inquiries seeking technical clarification, steps, or explanations. | Wh-words, question marks, "how to", "why did you", "what version". | `AUTO` (if answerable & grounded) or `DRAFT` (if unanswerable) |
| **`praise`** | Viewer compliments, gratitude, positive reinforcement, or encouragement. | "Great video", "thanks", "loved this", "helpful explanation". | `AUTO` (if short & safe) or `DRAFT` |
| **`complaint`** | Frustration regarding audio/video quality, broken code, or missing links. | "Audio is bad", "code broke", "waste of time", "link is 404". | **`ESCALATE` (Always)** |
| **`business_collab`** | Commercial outreach, sponsorships, product review requests, joint ventures. | "Sponsorship", "partnership", "affiliate", "email us at", "collab". | **`ESCALATE` (Always)** |
| **`technical_correction`** | Technical bug reports, API deprecation notices, syntax corrections. | "At MM:SS you made a mistake", "deprecated in v3", "typo on line 12". | **`ESCALATE` (Always)** |
| **`spam`** | Automated promotions, cryptocurrency scams, telegram groups, link farming. | "WhatsApp +1", "Telegram @", "free BTC", "make money fast", "bit.ly". | **`ESCALATE` (Flagged, Zero Reply)** |
| **`sensitive`** | Content moderation triggers: self-harm, legal threats, harassment, hate speech. | Mentions of self-harm, lawyer/legal action, harassment. | **`ESCALATE` (Always)** |

---

## 2. Question Sub-Types: Answerable vs. Unanswerable

### Answerable (`is_answerable = True`)
- The question's direct, factual answer exists in the video transcript `data/sample_transcripts/vid_101.txt`.
- *Example:* "What Python version do I need?" $\rightarrow$ Answerable (`[00:45]` mentions Python 3.11 or 3.12).
- *Expected Model Behavior:* Cite `[00:45]` and generate a concise reply.

### Unanswerable (`is_answerable = False`)
- The question asks about topics, future plans, tools, or pricing never mentioned in the transcript.
- *Example:* "Are you going to make a Flutter tutorial next month?"
- *Expected Model Behavior:* Strictly output `ABSTAIN`. Must **never** hallucinate or speculate.

---

## 3. Dataset Splits & Tuning Rules
- **Validation Split (30 comments)**: Used to tune confidence thresholds and retrieval cutoff scores.
- **Test Split (70 comments)**: Held out completely during development. Evaluated **exactly once** to report unbiased generalization performance.

