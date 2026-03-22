"""
Inference Engine — assembles final AnalyzeResponse from all pipeline outputs.
Now includes spam analysis in result and summaries.
"""

from models import (
    NLPResult, ExtractedResource, FileType, ResultCase,
    AnalyzeResponse, SpamAnalysis, TopComment, TopEmoji
)

_ACTION_TEMPLATES = {
    "pdf":        "Comment '{kw}' on the reel to automatically receive a PDF via DM",
    "ebook":      "Comment '{kw}' on the reel to receive a free eBook via DM",
    "guide":      "Comment '{kw}' on the reel to receive the guide via DM",
    "link":       "Comment '{kw}' on the reel to receive the resource link via DM",
    "template":   "Comment '{kw}' on the reel to receive the template via DM",
    "checklist":  "Comment '{kw}' on the reel to receive the checklist via DM",
    "cheatsheet": "Comment '{kw}' on the reel to receive the cheat sheet via DM",
    "blueprint":  "Comment '{kw}' on the reel to receive the blueprint via DM",
    "course":     "Comment '{kw}' on the reel to receive access to the course via DM",
    "video":      "Comment '{kw}' on the reel to receive the video link via DM",
    "freebie":    "Comment '{kw}' on the reel to claim your free resource via DM",
    "default":    "Comment '{kw}' on the reel to automatically receive the resource via DM",
}


def _best_action(keywords: list[str]) -> tuple[str, str]:
    for kw in keywords:
        for key in _ACTION_TEMPLATES:
            if key in kw.lower():
                return kw, _ACTION_TEMPLATES[key].replace("{kw}", kw)
    kw = keywords[0] if keywords else "keyword"
    return kw, _ACTION_TEMPLATES["default"].replace("{kw}", kw)


def resolve_result_case(nlp: NLPResult, resources: list[ExtractedResource]) -> ResultCase:
    if any(r.file_type != FileType.NONE for r in resources):
        return ResultCase.FILE_FOUND
    if resources:
        return ResultCase.LINK_FOUND
    if nlp.automation_detected:
        return ResultCase.AUTOMATION_DETECTED
    return ResultCase.NO_AUTOMATION


def _build_spam_analysis_from_meta(metadata: dict) -> SpamAnalysis:
    raw = metadata.get("spam_analysis", {})
    if not raw:
        return SpamAnalysis()
    return SpamAnalysis(
        top_comments=[TopComment(**c) for c in raw.get("top_comments", [])],
        top_emojis=[TopEmoji(**e) for e in raw.get("top_emojis", [])],
        spam_score=raw.get("spam_score", 0),
        total_comments=raw.get("total_comments", 0),
    )


def _build_summary(rc: ResultCase, nlp: NLPResult, resources: list[ExtractedResource],
                   spam: SpamAnalysis, suggested_action: str | None) -> str:
    spam_note = ""
    if spam.total_comments > 0:
        spam_note = (
            f" Analyzed {spam.total_comments} comments "
            f"({spam.spam_score}% repetition rate)."
        )

    match rc:
        case ResultCase.FILE_FOUND:
            ft = next((r.file_type.value.upper() for r in resources if r.file_type != FileType.NONE), "File")
            return f"Automated {ft} distribution detected ({nlp.confidence_score}% confidence). Direct file link extracted.{spam_note}"
        case ResultCase.LINK_FOUND:
            return f"Automation pattern detected ({nlp.confidence_score}% confidence). {len(resources)} resource link(s) extracted.{spam_note}"
        case ResultCase.AUTOMATION_DETECTED:
            kws = ", ".join(f"'{k}'" for k in nlp.trigger_keywords[:3])
            return (
                f"Automation trigger detected ({nlp.confidence_score}% confidence) "
                f"via keyword(s): {kws}. No direct link found — "
                f"resource likely distributed via DM bot.{spam_note}"
            )
        case ResultCase.NO_AUTOMATION:
            return f"No automation patterns detected.{spam_note}"
        case _:
            return "Analysis complete."


def build_response(post_url: str, nlp: NLPResult, resources: list[ExtractedResource],
                   metadata: dict = {}, processing_time_ms: int = 0,
                   error: str | None = None) -> AnalyzeResponse:

    result_case = resolve_result_case(nlp, resources)

    file_resources = [r for r in resources if r.file_type != FileType.NONE]
    link_resources = [r for r in resources if r.file_type == FileType.NONE]

    download_link: str | None = None
    file_type = FileType.NONE
    if file_resources:
        best = file_resources[0]
        download_link = best.resolved_url or best.url
        file_type = best.file_type

    extracted_links = [r.resolved_url or r.url for r in link_resources]

    suggested_action: str | None = None
    if result_case == ResultCase.AUTOMATION_DETECTED and nlp.trigger_keywords:
        _, suggested_action = _best_action(nlp.trigger_keywords)
    elif result_case == ResultCase.NO_AUTOMATION and nlp.spam_signals:
        # Even without text keywords, spam pattern is suspicious
        suggested_action = "High comment activity detected — may use emoji-based DM automation"

    spam_analysis = _build_spam_analysis_from_meta(metadata)
    summary = _build_summary(result_case, nlp, resources, spam_analysis, suggested_action)

    return AnalyzeResponse(
        automation_detected=nlp.automation_detected,
        result_case=result_case,
        trigger_keywords=nlp.trigger_keywords,
        confidence_score=nlp.confidence_score,
        matched_patterns=nlp.matched_patterns,
        spam_signals=nlp.spam_signals,
        spam_analysis=spam_analysis,
        file_type=file_type,
        download_link=download_link,
        extracted_links=extracted_links,
        all_resources=resources,
        suggested_action=suggested_action,
        post_url=post_url,
        analysis_summary=summary,
        processing_time_ms=processing_time_ms,
        error=error,
    )