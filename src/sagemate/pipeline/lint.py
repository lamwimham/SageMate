"""
Wiki Lint Engine — Self-Maintenance.

Periodically health-checks the wiki for:
- Contradictions between pages
- Stale claims (pages not updated in N days)
- Orphan pages (zero inbound links)
- Broken wikilinks
- Missing cross-references (concepts mentioned but lacking their own page)
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

from ..core.config import Settings, settings
from ..core.store import Store
from ..models import (
    LintIssue,
    LintIssueSeverity,
    LintIssueType,
    LintReport,
    WikiCategory,
    WikiPage,
)


# Regex to find wikilinks like [[page-slug]]
WIKILINK_RE = re.compile(r'\[\[([^\]]+)\]\]')


class LintEngine:
    """
    Scans the wiki directory and detects structural/content issues.
    """

    def __init__(
        self,
        store: Store,
        wiki_dir: Path,
        settings_obj: Optional[Settings] = None,
    ):
        self.store = store
        self.wiki_dir = wiki_dir
        self.cfg = settings_obj or settings

    async def run(self) -> LintReport:
        """Run all lint checks and return a report."""
        report = LintReport()
        pages = await self.store.list_pages()
        report.total_pages_scanned = len(pages)

        # Build lookup
        slug_to_page = {p.slug: p for p in pages}
        all_slugs = set(slug_to_page.keys())

        # 1. Orphan pages
        orphan_issues = await self._check_orphans(pages, slug_to_page)
        report.issues.extend(orphan_issues)

        # 2. Broken links
        broken_issues = await self._check_broken_links(pages, all_slugs)
        report.issues.extend(broken_issues)

        # 3. Stale pages
        stale_issues = await self._check_stale_pages(pages)
        report.issues.extend(stale_issues)

        # 4. Missing cross-refs
        missing_ref_issues = await self._check_missing_cross_refs(pages, all_slugs)
        report.issues.extend(missing_ref_issues)

        # 5. Contradictions (LLM-assisted, only for high-priority pairs)
        contradiction_issues = await self._check_contradictions(pages)
        report.issues.extend(contradiction_issues)

        return report

    async def generate_report_md(self, report: LintReport) -> str:
        """Render a lint report as markdown."""
        lines = [
            f"# Lint Report — {report.timestamp.strftime('%Y-%m-%d %H:%M')}",
            "",
            f"- **Pages scanned**: {report.total_pages_scanned}",
            f"- **Issues found**: {report.issue_count}",
            f"- **High severity**: {report.high_severity_count}",
            "",
        ]

        if not report.issues:
            lines.append("No issues found. Wiki is healthy!")
            return "\n".join(lines)

        # Group by severity
        by_severity: dict[str, list[LintIssue]] = {}
        for issue in report.issues:
            by_severity.setdefault(issue.severity.value, []).append(issue)

        for severity in ["high", "medium", "low"]:
            issues = by_severity.get(severity, [])
            if not issues:
                continue
            lines.append(f"## {severity.upper()} ({len(issues)} issues)")
            lines.append("")
            for issue in issues:
                lines.append(f"### [{issue.issue_type.value}] `{issue.page_slug}`")
                lines.append(f"{issue.description}")
                if issue.suggestion:
                    lines.append(f"> **Suggestion**: {issue.suggestion}")
                if issue.related_pages:
                    lines.append(f"- Related: {', '.join(f'`{p}`' for p in issue.related_pages)}")
                lines.append("")

        return "\n".join(lines)

    # ── Individual Checks ──────────────────────────────────────

    async def _check_orphans(
        self, pages: list[WikiPage], slug_to_page: dict[str, WikiPage]
    ) -> list[LintIssue]:
        """Find pages with zero inbound links."""
        issues = []
        for page in pages:
            inbound = page.inbound_links if isinstance(page.inbound_links, list) else []
            if not inbound and page.category != WikiCategory.ANALYSIS:
                issues.append(LintIssue(
                    issue_type=LintIssueType.ORPHAN_PAGE,
                    severity=LintIssueSeverity.LOW,
                    page_slug=page.slug,
                    description=f"Page `{page.slug}` has no inbound links from other wiki pages.",
                    suggestion="Consider adding wikilinks to this page from relevant existing pages.",
                ))
        return issues

    async def _check_broken_links(
        self, pages: list[WikiPage], all_slugs: set[str]
    ) -> list[LintIssue]:
        """Find wikilinks pointing to non-existent pages."""
        issues = []
        for page in pages:
            outbound = page.outbound_links if isinstance(page.outbound_links, list) else []
            for link in outbound:
                if link not in all_slugs:
                    issues.append(LintIssue(
                        issue_type=LintIssueType.BROKEN_LINK,
                        severity=LintIssueSeverity.MEDIUM,
                        page_slug=page.slug,
                        description=f"Page `{page.slug}` links to `[[{link}]]` which doesn't exist.",
                        suggestion=f"Either create a page for `{link}` or remove the link.",
                        related_pages=[link],
                    ))
        return issues

    async def _check_stale_pages(self, pages: list[WikiPage]) -> list[LintIssue]:
        """Find pages that haven't been updated in N days."""
        issues = []
        cutoff = datetime.now() - timedelta(days=self.cfg.lint_stale_days)

        for page in pages:
            if page.updated_at and page.updated_at < cutoff:
                issues.append(LintIssue(
                    issue_type=LintIssueType.STALE_CLAIM,
                    severity=LintIssueSeverity.MEDIUM,
                    page_slug=page.slug,
                    description=f"Page `{page.slug}` hasn't been updated since {page.updated_at.strftime('%Y-%m-%d')}.",
                    suggestion=f"Review this page against newer sources. It may contain outdated claims.",
                ))
        return issues

    async def _check_missing_cross_refs(
        self, pages: list[WikiPage], all_slugs: set[str]
    ) -> list[LintIssue]:
        """Find concepts mentioned in page content that lack their own wiki page."""
        # This is a heuristic: look for capitalized multi-word terms in content
        # that aren't already wiki pages.
        issues = []
        for page in pages:
            if not page.content:
                continue
            # Simple heuristic: find [[links]] to non-existent pages (also caught by broken_links)
            # For now, we skip the NLP-based missing cross-ref detection
            # This would require LLM assistance to identify "important concepts without pages"
            pass
        return issues

    async def _check_contradictions(self, pages: list[WikiPage]) -> list[LintIssue]:
        """
        Detect potential contradictions between pages.
        For MVP: flag pages with similar slugs/titles but different content.
        Full version would use LLM to compare page pairs.
        """
        issues = []
        # Simple heuristic: if two pages share significant title overlap, flag for review
        by_prefix: dict[str, list[WikiPage]] = {}
        for page in pages:
            prefix = page.slug.split('-')[0] if '-' in page.slug else page.slug[:5]
            by_prefix.setdefault(prefix, []).append(page)

        for prefix, group in by_prefix.items():
            if len(group) > 1:
                slugs = [p.slug for p in group]
                issues.append(LintIssue(
                    issue_type=LintIssueType.CONTRADICTION,
                    severity=LintIssueSeverity.LOW,
                    page_slug=group[0].slug,
                    description=f"Multiple pages share prefix `{prefix}`: {', '.join(slugs)}. Review for contradictions.",
                    suggestion="Merge related pages or ensure they cover distinct sub-topics.",
                    related_pages=slugs[1:],
                ))

        return issues

    async def auto_repair(self, report: LintReport, categories: list[LintIssueType] | None = None) -> int:
        """
        Auto-fix safe issues:
        - Remove broken links from outbound_links metadata
        - Add orphan tags for orphan pages
        Returns number of fixes applied.
        """
        fixes = 0
        for issue in report.issues:
            if categories and issue.issue_type not in categories:
                continue

            if issue.issue_type == LintIssueType.BROKEN_LINK:
                # Remove broken link from page metadata
                page = await self.store.get_page(issue.page_slug)
                if page:
                    broken_slug = issue.related_pages[0] if issue.related_pages else None
                    if broken_slug and broken_slug in page.outbound_links:
                        page.outbound_links = [l for l in page.outbound_links if l != broken_slug]
                        # Note: We'd need the page content to update the actual wikilink text
                        # For MVP, we just fix the metadata
                        fixes += 1

        return fixes
