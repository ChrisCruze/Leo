"""
Shared report generation module for campaign scripts.

This module provides a standardized way to generate markdown reports
for all campaign scripts (fill-the-table, return-to-table, seat-newcomers).
"""

from typing import List, Dict, Any, Optional


def generate_report(
    users: List[Dict[str, Any]],
    events: List[Dict[str, Any]],
    matches: List[Dict[str, Any]],
    messages: List[Dict[str, Any]],
    goal: str,
    campaign_id: str,
    campaign_name: str,
    user_filtering_explanation: str,
    event_filtering_explanation: str,
    matching_prompt: str,
    message_generation_prompt: str,
    assessment: Optional[Dict[str, Any]] = None,
    recommendations: Optional[List[str]] = None,
    user_display_fields: Optional[Dict[str, str]] = None,
    event_display_fields: Optional[Dict[str, str]] = None
) -> str:
    """
    Generate a markdown report for a campaign.
    
    Args:
        users: List of filtered user dictionaries (must have 'summary' field)
        events: List of filtered event dictionaries (must have 'summary' field)
        matches: List of match dictionaries
        messages: List of message dictionaries
        goal: Campaign goal statement
        campaign_id: Unique campaign identifier
        campaign_name: Campaign name (e.g., 'fill-the-table')
        user_filtering_explanation: Explanation of how users were filtered
        event_filtering_explanation: Explanation of how events were filtered
        matching_prompt: The prompt template used for matching users to events
        message_generation_prompt: The prompt template used for generating messages
        assessment: Optional assessment dictionary with 'assessment', 'strengths', 'recommendations', 'focus_areas'
        recommendations: Optional list of recommendation strings (alternative to assessment)
        user_display_fields: Optional dict mapping field names to display labels for user listings
        event_display_fields: Optional dict mapping field names to display labels for event listings
    
    Returns:
        Markdown string ready to be written to file
    """
    content = []
    
    # Goal section
    content.append(f"# Goal\n{goal}\n")
    
    # Run Summary
    content.extend([
        "## Run Summary",
        f"- Campaign ID: `{campaign_id}`",
        f"- Users processed: {len(users)}",
        f"- Events processed: {len(events)}",
        f"- Matches: {len(matches)}",
        f"- Messages: {len(messages)}",
        ""
    ])
    
    # Filtered Users section
    content.extend(_generate_users_section(users, user_filtering_explanation, user_display_fields))
    
    # Filtered Events section
    content.extend(_generate_events_section(events, event_filtering_explanation, event_display_fields))
    
    # Matches section
    content.extend(_generate_matches_section(matches))
    
    # Messages section
    content.extend(_generate_messages_section(messages))
    
    # Key Prompts section
    content.extend(_generate_prompts_section(matching_prompt, message_generation_prompt))
    
    # Assessment & Recommendations section
    if assessment or recommendations:
        content.extend(_generate_assessment_section(assessment, recommendations))
    
    return "\n".join(content)


def _generate_users_section(
    users: List[Dict[str, Any]],
    filtering_explanation: str,
    display_fields: Optional[Dict[str, str]] = None
) -> List[str]:
    """Generate users section with summaries and filtering explanation."""
    content = [
        "## Filtered Users",
        f"**How users were filtered:** {filtering_explanation}",
        "",
        "### User Details"
    ]
    
    if not users:
        content.append("- None")
        return content
    
    user_lines = []
    for i, u in enumerate(users, 1):
        name = f"{u.get('firstName', '')} {u.get('lastName', '')}".strip() or 'Unknown'
        summary = u.get('summary', 'No summary available')
        
        # Build display info based on available fields
        info_parts = []
        
        # Check for common score fields
        if 'newcomer_score' in u:
            info_parts.append(f"score: {u.get('newcomer_score', 0)}")
        elif 'reactivation_score' in u:
            info_parts.append(f"score: {u.get('reactivation_score', 0)}")
        
        # Check for event count
        if 'eventCount' in u:
            event_count = u.get('eventCount', 0)
            label = display_fields.get('eventCount', 'events') if display_fields else 'events'
            info_parts.append(f"{label}: {event_count}")
        
        # Check for days inactive
        if 'days_inactive' in u:
            days = u.get('days_inactive', 0)
            label = display_fields.get('days_inactive', 'days inactive') if display_fields else 'days inactive'
            info_parts.append(f"{label}: {days}")
        
        # Check for days since join
        if 'days_since_join' in u:
            days = u.get('days_since_join', 0)
            label = display_fields.get('days_since_join', 'days since join') if display_fields else 'days since join'
            info_parts.append(f"{label}: {days}")
        
        # Check for first timer status
        if 'is_first_timer' in u:
            if u.get('is_first_timer'):
                info_parts.append("FIRST-TIMER")
            else:
                event_count = u.get('eventCount', 0)
                info_parts.append(f"{event_count} events")
        
        # Add neighborhood
        neighborhood = u.get('homeNeighborhood', 'N/A')
        if neighborhood and neighborhood != 'N/A':
            info_parts.append(f"neighborhood: {neighborhood}")
        
        info_str = " | ".join(info_parts) if info_parts else ""
        
        user_lines.append(
            f"{i}. **{name}**" + (f" | {info_str}" if info_str else "") + f"\n   - **Summary:** {summary}"
        )
    
    content.append("\n".join(user_lines))
    content.append("")  # Empty line after section
    
    return content


def _generate_events_section(
    events: List[Dict[str, Any]],
    filtering_explanation: str,
    display_fields: Optional[Dict[str, str]] = None
) -> List[str]:
    """Generate events section with summaries and filtering explanation."""
    content = [
        "## Filtered Events",
        f"**How events were filtered:** {filtering_explanation}",
        "",
        "### Event Details"
    ]
    
    if not events:
        content.append("- None")
        return content
    
    event_lines = []
    for i, e in enumerate(events, 1):
        event_name = e.get('name', 'N/A')
        start_date = e.get('startDate', 'TBD')
        neighborhood = e.get('neighborhood', 'N/A')
        
        participants = len(e.get('participants', [])) if isinstance(e.get('participants'), list) else 0
        maxp = e.get('maxParticipants', 0)
        fill_pct = e.get('participationPercentage', 0)
        
        summary = e.get('summary', 'No summary available')
        
        event_lines.append(
            f"{i}. **{event_name}** | start: {start_date} | neighborhood: {neighborhood} | "
            f"capacity: {maxp} | participants: {participants} ({fill_pct:.1f}% full)\n"
            f"   - **Summary:** {summary}"
        )
    
    content.append("\n".join(event_lines))
    content.append("")  # Empty line after section
    
    return content


def _generate_matches_section(matches: List[Dict[str, Any]]) -> List[str]:
    """Generate matches section with reasoning."""
    content = [
        "## Matches and Reasoning"
    ]
    
    if not matches:
        content.append("- None")
        content.append("")
        return content
    
    match_lines = []
    for m in matches:
        user_name = m.get('user_name', 'Unknown')
        event_name = m.get('event_name', 'Unknown')
        confidence = m.get('confidence_percentage', 0)
        reasoning = m.get('reasoning', 'No reasoning provided')
        
        match_lines.append(
            f"1. {user_name} → {event_name} ({confidence}%)\n   Reasoning: {reasoning}"
        )
    
    content.append("\n".join(match_lines))
    content.append("")  # Empty line after section
    
    return content


def _generate_messages_section(messages: List[Dict[str, Any]]) -> List[str]:
    """Generate messages section."""
    content = [
        "## Messages"
    ]
    
    if not messages:
        content.append("- None")
        content.append("")
        return content
    
    msg_lines = []
    for m in messages:
        user_name = m.get('user_name', 'Unknown')
        confidence = m.get('confidence_percentage', m.get('similarity_score', 0))
        message_text = m.get('message_text', '')
        reasoning = m.get('reasoning', '')
        
        if reasoning:
            msg_lines.append(
                f"1. {user_name} ({confidence}%) - {message_text}\n   Reasoning: {reasoning}"
            )
        else:
            msg_lines.append(
                f"1. {user_name} ({confidence}%) - {message_text}"
            )
    
    content.append("\n".join(msg_lines))
    content.append("")  # Empty line after section
    
    return content


def _generate_prompts_section(matching_prompt: str, message_generation_prompt: str) -> List[str]:
    """Generate prompts section with code blocks."""
    return [
        "## Key Prompts Used",
        "",
        "### Matching Prompt",
        "```",
        matching_prompt,
        "```",
        "",
        "### Message Generation Prompt",
        "```",
        message_generation_prompt,
        "```",
        ""
    ]


def _generate_assessment_section(
    assessment: Optional[Dict[str, Any]] = None,
    recommendations: Optional[List[str]] = None
) -> List[str]:
    """Generate assessment and recommendations section."""
    content = [
        "## Assessment & Recommendations"
    ]
    
    if assessment:
        content.append("")
        content.append(f"**Assessment:** {assessment.get('assessment', 'N/A')}")
        content.append("")
        
        strengths = assessment.get('strengths', [])
        if strengths:
            content.append("**Strengths:**")
            for strength in strengths:
                content.append(f"- {strength}")
            content.append("")
        
        recs = assessment.get('recommendations', [])
        if recs:
            content.append("**Recommendations:**")
            for rec in recs:
                content.append(f"- {rec}")
            content.append("")
        
        focus_areas = assessment.get('focus_areas', [])
        if focus_areas:
            content.append("**Focus Areas:**")
            for area in focus_areas:
                content.append(f"- {area}")
            content.append("")
    elif recommendations:
        content.append("")
        for rec in recommendations:
            content.append(f"- {rec}")
        content.append("")
    else:
        content.append("- No assessment or recommendations available.")
        content.append("")
    
    return content
