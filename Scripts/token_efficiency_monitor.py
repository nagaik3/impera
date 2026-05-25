#!/usr/bin/env python3
"""
Token Efficiency Monitor for EXODUS Claude Sessions

Tracks token usage across sessions and provides recommendations.
Usage: python3 ~/Scripts/token_efficiency_monitor.py [options]
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
OBSIDIAN_VAULT = Path.home() / "Obsidian/EXODUS"
DAILY_NOTES_DIR = OBSIDIAN_VAULT / "Daily-Notes"
EFFICIENCY_GUIDE = OBSIDIAN_VAULT / "03-Resources/Operations/Token-Efficiency-Guide.md"
CHECKLIST = OBSIDIAN_VAULT / "03-Resources/Operations/Session-Efficiency-Checklist.md"

# Token cost benchmarks
TOKEN_COSTS = {
    "read_file": 3.0,  # per file, estimated
    "smart_search": 0.8,
    "smart_outline": 1.0,
    "smart_unfold": 1.2,
    "grep": 0.05,
    "edit": 0.5,
    "bash": 0.2,
    "monitor": 0.05,  # per event
}

MONTHLY_BUDGET = 200000  # tokens
TARGET_SESSION = 20000  # tokens


def get_session_dates(days=30):
    """Get list of session dates from last N days."""
    today = datetime.now()
    dates = []
    for i in range(days):
        date = today - timedelta(days=i)
        dates.append(date.strftime("%Y-%m-%d"))
    return dates


def count_tool_usage_in_notes():
    """Estimate token usage from daily notes."""
    if not DAILY_NOTES_DIR.exists():
        print("❌ Daily-Notes directory not found")
        return {}

    usage = {
        "read_count": 0,
        "smart_search_count": 0,
        "smart_outline_count": 0,
        "smart_unfold_count": 0,
        "grep_count": 0,
        "edit_count": 0,
        "bash_count": 0,
        "monitor_count": 0,
        "estimated_tokens": 0,
    }

    # Count mentions of each tool type in recent notes
    for note_file in sorted(DAILY_NOTES_DIR.glob("*.md"), reverse=True)[:5]:
        with open(note_file, 'r') as f:
            content = f.read().lower()

        # Count tool usage patterns
        usage["read_count"] += content.count("read(")
        usage["smart_search_count"] += content.count("smart_search")
        usage["smart_outline_count"] += content.count("smart_outline")
        usage["smart_unfold_count"] += content.count("smart_unfold")
        usage["grep_count"] += content.count("grep")
        usage["edit_count"] += content.count("edit(")
        usage["bash_count"] += content.count("bash(")
        usage["monitor_count"] += content.count("monitor")

    # Calculate estimated tokens
    usage["estimated_tokens"] = (
        usage["read_count"] * TOKEN_COSTS["read_file"] +
        usage["smart_search_count"] * TOKEN_COSTS["smart_search"] +
        usage["smart_outline_count"] * TOKEN_COSTS["smart_outline"] +
        usage["smart_unfold_count"] * TOKEN_COSTS["smart_unfold"] +
        usage["grep_count"] * TOKEN_COSTS["grep"] +
        usage["edit_count"] * TOKEN_COSTS["edit"] +
        usage["bash_count"] * TOKEN_COSTS["bash"] +
        usage["monitor_count"] * TOKEN_COSTS["monitor"]
    )

    return usage


def print_efficiency_report():
    """Print token efficiency report."""
    print("\n" + "="*60)
    print("⚡ EXODUS Token Efficiency Monitor")
    print("="*60)

    usage = count_tool_usage_in_notes()

    if not usage["estimated_tokens"]:
        print("\n⚠️  No recent session data found.")
        print("→ Create Daily-Notes/YYYY-MM-DD.md entries to track usage\n")
        return

    avg_session = usage["estimated_tokens"] / 5 if usage else 0
    monthly_projection = avg_session * 20  # ~20 sessions/month

    # Display report
    print(f"\n📊 Tool Usage (Last 5 sessions):")
    print(f"   Read() calls:         {usage['read_count']:>3} (@ {TOKEN_COSTS['read_file']:.1f}k tokens)")
    print(f"   smart_search() calls: {usage['smart_search_count']:>3} (@ {TOKEN_COSTS['smart_search']:.1f}k tokens)")
    print(f"   smart_outline() calls:{usage['smart_outline_count']:>3} (@ {TOKEN_COSTS['smart_outline']:.1f}k tokens)")
    print(f"   smart_unfold() calls: {usage['smart_unfold_count']:>3} (@ {TOKEN_COSTS['smart_unfold']:.1f}k tokens)")
    print(f"   grep/Bash calls:      {usage['grep_count']:>3} (@ {TOKEN_COSTS['grep']:.2f}k tokens)")
    print(f"   Edit() calls:         {usage['edit_count']:>3} (@ {TOKEN_COSTS['edit']:.1f}k tokens)")
    print(f"   Bash() calls:         {usage['bash_count']:>3} (@ {TOKEN_COSTS['bash']:.1f}k tokens)")
    print(f"   Monitor events:       {usage['monitor_count']:>3} (@ {TOKEN_COSTS['monitor']:.2f}k tokens)")

    print(f"\n💾 Token Usage Estimate:")
    print(f"   Total (5 sessions):   {usage['estimated_tokens']:>7.1f}k tokens")
    print(f"   Avg per session:      {avg_session:>7.1f}k tokens")
    print(f"   Monthly projection:   {monthly_projection:>7.1f}k tokens")
    print(f"   Target per session:   {TARGET_SESSION:>7.1f}k tokens")
    print(f"   Monthly budget:       {MONTHLY_BUDGET:>7.1f}k tokens")

    # Assessment
    print(f"\n📈 Assessment:")
    if avg_session <= TARGET_SESSION:
        pct_of_target = (avg_session / TARGET_SESSION) * 100
        print(f"   ✅ {pct_of_target:.0f}% of target ({avg_session:.1f}k avg)")
        print(f"   📊 On track for ${(monthly_projection * 0.000005):.2f}/month")
    else:
        over_target = avg_session - TARGET_SESSION
        print(f"   ⚠️  {(avg_session/TARGET_SESSION):.1%} of target (over by {over_target:.1f}k)")
        print(f"   💰 Monthly cost: ${(monthly_projection * 0.000005):.2f}/month")

    # Recommendations
    print(f"\n🎯 Recommendations:")
    if usage["read_count"] > usage["smart_search_count"]:
        print(f"   • Use smart_search() more (saves 70% vs Read())")
    if usage["grep_count"] < 5:
        print(f"   • Use grep/Bash for quick searches (saves 95%)")
    if usage["edit_count"] > 5:
        print(f"   • Consolidate edits into batches")
    if usage["bash_count"] < 3:
        print(f"   • Use Bash for exploration (very cheap)")

    print(f"\n📚 Resources:")
    print(f"   📖 Token Efficiency Guide: [[Token-Efficiency-Guide]]")
    print(f"   ✅ Session Checklist:      [[Session-Efficiency-Checklist]]")
    print(f"\n{'='*60}\n")


def print_quick_tips():
    """Print quick efficiency tips."""
    print("\n💡 Quick Efficiency Tips:")
    print("   1. smart_search() to FIND code (0.8k tokens)")
    print("   2. smart_outline() to SEE structure (1.0k tokens)")
    print("   3. smart_unfold() to READ function (1.2k tokens)")
    print("   4. grep for SEARCH text (0.05k tokens)")
    print("   5. Monitor for WATCH logs (0.05k per event)")
    print("   6. Consolidate reads into one batch")
    print("   7. Trust context, don't re-read")
    print()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "--tips":
            print_quick_tips()
        elif sys.argv[1] == "--help":
            print(__doc__)
        else:
            print(f"Unknown option: {sys.argv[1]}")
            print("Usage: python3 token_efficiency_monitor.py [--tips|--help]")
    else:
        print_efficiency_report()
