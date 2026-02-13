#!/usr/bin/env python3
"""
DocuMind Demo — one-command AI contract analysis.

Usage:
    python demo.py <file>

Examples:
    python demo.py sample_contract.txt
    python demo.py my_lease.pdf
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

# ── ANSI colours for terminal output ──────────────────────────────────────────

BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"

RISK_COLOURS = {
    "CRITICAL": RED,
    "HIGH": YELLOW,
    "MEDIUM": MAGENTA,
    "LOW": GREEN,
}

USAGE = f"""\
{BOLD}DocuMind Demo{RESET} — AI-powered contract clause analysis

{BOLD}Usage:{RESET}  python demo.py <file>

{BOLD}Examples:{RESET}
  python demo.py sample_contract.txt     # bundled sample SaaS agreement
  python demo.py my_lease.pdf            # your own PDF (requires PyPDF2)

{BOLD}Setup:{RESET}
  1. Copy .env.example to .env and set your AI_API_KEY
  2. pip install -e "."          # core dependencies
  3. pip install -e ".[pdf]"     # optional, for PDF support
"""


def read_file(path: Path) -> str:
    """Read a file and return its text content."""
    if path.suffix.lower() == ".pdf":
        try:
            import PyPDF2  # noqa: F811
        except ImportError:
            print(
                f"{RED}PyPDF2 is required for PDF files.{RESET}\n"
                f"Install it with: pip install -e \".[pdf]\""
            )
            sys.exit(1)

        reader = PyPDF2.PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(pages)
    else:
        text = path.read_text(encoding="utf-8")

    if not text.strip():
        print(f"{RED}Error:{RESET} File is empty or could not be read: {path}")
        sys.exit(1)

    return text


def print_results(result) -> None:
    """Pretty-print the AI extraction results."""
    meta = result.metadata

    # ── Header ────────────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print(f"{BOLD}{CYAN}  CONTRACT ANALYSIS RESULTS{RESET}")
    print(f"{'=' * 70}\n")

    print(f"  {BOLD}Contract type:{RESET}   {meta.contract_type}")
    print(f"  {BOLD}Language:{RESET}        {result.language}")
    print(f"  {BOLD}Parties:{RESET}         {', '.join(meta.parties_involved)}")
    if meta.effective_date:
        print(f"  {BOLD}Effective date:{RESET}  {meta.effective_date}")
    print(f"  {BOLD}Clauses found:{RESET}   {meta.total_clauses_found}")

    # ── Clauses ───────────────────────────────────────────────────────────
    print(f"\n{'-' * 70}")
    print(f"{BOLD}  EXTRACTED CLAUSES{RESET}")
    print(f"{'-' * 70}")

    risk_counts: dict[str, int] = {}

    for i, clause in enumerate(result.clauses, 1):
        colour = RISK_COLOURS.get(clause.risk_level, RESET)
        risk_counts[clause.risk_level] = risk_counts.get(clause.risk_level, 0) + 1

        print(f"\n  {BOLD}#{i}{RESET}  {clause.title}")
        print(f"      Type:       {clause.clause_type}")
        print(f"      Risk:       {colour}{BOLD}{clause.risk_level}{RESET}")
        print(f"      Confidence: {clause.confidence_score:.0%}")

        # Word-wrap the summary to ~64 chars
        words = clause.summary.split()
        lines: list[str] = []
        line = ""
        for w in words:
            if line and len(line) + len(w) + 1 > 64:
                lines.append(line)
                line = w
            else:
                line = f"{line} {w}" if line else w
        if line:
            lines.append(line)

        print(f"      Summary:    {lines[0]}")
        for ln in lines[1:]:
            print(f"                  {ln}")

    # ── Summary stats ─────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print(f"{BOLD}  RISK SUMMARY{RESET}\n")
    for level in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        count = risk_counts.get(level, 0)
        if count:
            colour = RISK_COLOURS[level]
            print(f"    {colour}{BOLD}{level:<10}{RESET} {count} clause{'s' if count != 1 else ''}")
    print(f"\n    {DIM}Total: {len(result.clauses)} clauses analysed{RESET}")
    print(f"{'=' * 70}\n")


async def run(file_path: Path) -> None:
    # ── 1. Read the file ──────────────────────────────────────────────────
    print(f"\n{DIM}Reading {file_path.name} ...{RESET}")
    document_text = read_file(file_path)
    print(f"{DIM}Read {len(document_text):,} characters.{RESET}")

    # ── 2. Load settings ─────────────────────────────────────────────────
    from src.config import Settings

    settings = Settings()

    if not settings.AI_API_KEY:
        print(
            f"\n{RED}{BOLD}Error:{RESET} AI_API_KEY is not set.\n\n"
            f"  1. Copy .env.example to .env\n"
            f"  2. Add your API key:  AI_API_KEY=sk-...\n"
        )
        sys.exit(1)

    # ── 3. Build prompt and call AI ───────────────────────────────────────
    from src.prompts.clause_extraction import build_extraction_prompt, validate_ai_response
    from src.services.ai_client import create_ai_client

    messages = build_extraction_prompt(document_text)
    client = create_ai_client(settings.AI_PROVIDER, settings.AI_API_KEY, timeout=120)

    model = settings.AI_MODEL
    print(f"{DIM}Sending to {settings.AI_PROVIDER} ({model}) ...{RESET}")

    start = time.perf_counter()
    async with client:
        raw_response = await client.complete(messages, model)
    elapsed = time.perf_counter() - start

    print(f"{DIM}Response received in {elapsed:.1f}s.{RESET}")

    # ── 4. Validate and display ───────────────────────────────────────────
    result = validate_ai_response(raw_response)
    print_results(result)


def main() -> None:
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(1)

    file_path = Path(sys.argv[1])
    if not file_path.exists():
        print(f"{RED}Error:{RESET} File not found: {file_path}")
        sys.exit(1)

    asyncio.run(run(file_path))


if __name__ == "__main__":
    main()
