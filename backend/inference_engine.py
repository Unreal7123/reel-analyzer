"""
Inference Engine

When no direct link or file is found but automation is detected,
this module infers the likely automation flow and generates a
human-readable suggested_action and analysis_summary.
"""

from models import NLPResult, ExtractedResource, FileType, ResultCase, AnalyzeResponse

# ─── Templates ────────────────────────────────────────────────────────────────

_ACTION_TEMPLATES: dict[str, str] = {
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
    "default":    "Comment '{kw}' on the reel to automatically receive the resource via DM",
}


def _best_template(keywords: list[str]) -> tuple[str, str]:
    """Pick the most descriptive template based on trigger keywords."""
    for kw in keywords:
        kw_lower = kw.lower()
        for key in _ACTION_TEMPLATES:
            if key in kw_lower:
                return kw, _ACTION_TEMPLATES[key].replace("{kw}", kw)
    # fallback
    kw = keywords[0] if keywords else "keyword"
    return kw, _ACTION_TEMPLATES["default"].replace("{kw}", kw)


# ─── Result case resolution ───────────────────────────────────────────────────

def resolve_result_case(
    nlp: NLPResult,
    resources: list[ExtractedResource],
) -> ResultCase:
    """Determine which of the 4 UI cases applies."""
    file_resources = [r for r in resources if r.file_type != FileType.NONE]
    link_resources = [r for r in resources if r.url]

    if file_resources:
        return ResultCase.FILE_FOUND
    if link_resources:
        return ResultCase.LINK_FOUND
    if nlp.automation_detected:
        return ResultCase.AUTOMATION_DETECTED
    return ResultCase.NO_AUTOMATION


# ─── Summary builder ──────────────────────────────────────────────────────────

def _build_summary(
    result_case: ResultCase,
    nlp: NLPResult,
    resources: list[ExtractedResource],
    suggested_action: str | None,
) -> str:
    match result_case:
        case ResultCase.FILE_FOUND:
            ft = next(
                (r.file_type.value.upper() for r in resources if r.file_type != FileType.NONE),
                "File",
            )
            return (
                f"Automated {ft} distribution detected with "
                f"{nlp.confidence_score}% confidence. "
                f"A direct file link was found and extracted."
            )
        case ResultCase.LINK_FOUND:
            count = len(resources)
            return (
                f"Automation pattern detected ({nlp.confidence_score}% confidence). "
                f"{count} resource link(s) extracted from post data."
            )
        case ResultCase.AUTOMATION_DETECTED:
            kw = ", ".join(f"'{k}'" for k in nlp.trigger_keywords[:3])
            return (
                f"Automation trigger detected ({nlp.confidence_score}% confidence) "
                f"using keyword(s): {kw}. "
                f"No direct link found — likely distributed via DM bot. "
                f"Suggested action: {suggested_action or 'N/A'}"
            )
        case ResultCase.NO_AUTOMATION:
            return (
                "No automation patterns detected. "
                "This post does not appear to use keyword-triggered DM automation."
            )
        case _:
            return "Analysis complete."


# ─── Main inference function ──────────────────────────────────────────────────

def build_response(
    post_url: str,
    nlp: NLPResult,
    resources: list[ExtractedResource],
    processing_time_ms: int = 0,
    error: str | None = None,
) -> AnalyzeResponse:
    """
    Combine NLP result + extracted resources into the final API response.
    Applies inference when no direct link is found.
    """
    result_case = resolve_result_case(nlp, resources)

    # Separate file resources from plain links
    file_resources = [r for r in resources if r.file_type != FileType.NONE]
    link_resources = [r for r in resources if r.file_type == FileType.NONE]

    # Best file resource
    download_link: str | None = None
    file_type = FileType.NONE
    if file_resources:
        best = file_resources[0]
        download_link = best.resolved_url or best.url
        file_type = best.file_type

    # All plain links
    extracted_links = [r.resolved_url or r.url for r in link_resources]

    # Suggested action (inference)
    suggested_action: str | None = None
    if result_case == ResultCase.AUTOMATION_DETECTED and nlp.trigger_keywords:
        _, suggested_action = _best_template(nlp.trigger_keywords)

    summary = _build_summary(result_case, nlp, resources, suggested_action)

    return AnalyzeResponse(
        automation_detected=nlp.automation_detected,
        result_case=result_case,
        trigger_keywords=nlp.trigger_keywords,
        confidence_score=nlp.confidence_score,
        matched_patterns=nlp.matched_patterns,
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
