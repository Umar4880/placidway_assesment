"""
Surgical, Production-Grade DOM Cleaner and HTML-to-Markdown Converter.
Engineered using evidence-based structural heuristics and decoupled site configuration:
1. Uses lxml parser for robust handling of malformed HTML trees.
2. Identifies content root (<main> -> <article> -> <body>) before cleaning.
3. Form unwrap protection: unwraps forms that enclose substantial body content.
4. Generic boilerplate elimination (scripts, styles, hidden elements, nav/footer inside root).
5. Two-pass read-only evaluation: marks elements in Pass 1, removes in Pass 2.
6. Multi-signal section scoring: eliminates CTAs only when length, link-density, and action URL agree.
7. Word-gluing prevention in table cells using explicit cell separator spaces.
8. Hierarchy-aware orphan heading pruning (prunes only when next_level <= current_level).
9. Audit metrics logging (text kept percentage, rules fired).
10. Canonical document metadata header injection.
"""

import re
import logging
from typing import Dict, Any, List, Set, Optional, Tuple
from urllib.parse import urlparse
from bs4 import BeautifulSoup, Tag
import markdownify

from src.ingestion.site_configs.placidway import PLACIDWAY_CONFIG, SiteCleanerConfig

logger = logging.getLogger(__name__)

# Core boilerplate tags safe to remove on any website
GENERIC_BOILERPLATE_TAGS = [
    "script",
    "style",
    "noscript",
    "iframe",
    "svg",
    "button",
    "input",
    "select",
    "textarea",
]


class DOMCleaner:
    """
    Production-grade DOM cleaner applying multi-signal heuristics and per-site configuration.
    """

    def __init__(self, config: Optional[SiteCleanerConfig] = None):
        self.config = config or PLACIDWAY_CONFIG

    def _find_content_root(self, soup: BeautifulSoup) -> Tag:
        """
        Identify the primary content root (<main> -> <article> -> <body>)
        before performing any cleaning operations.
        """
        main = soup.find("main")
        if main and len(main.get_text(strip=True)) > 200:
            return main

        article = soup.find("article")
        if article and len(article.get_text(strip=True)) > 200:
            return article

        body = soup.find("body")
        if body:
            return body

        return soup

    def _unwrap_or_strip_forms(self, root: Tag) -> None:
        """
        Handle forms intelligently: if a form wraps more than 50% of the root's text,
        unwrap it to preserve text. Otherwise, decompose it.
        """
        total_text_len = len(root.get_text(strip=True))
        for form in list(root.find_all("form")):
            if getattr(form, "attrs", None) is None:
                continue
            form_text_len = len(form.get_text(strip=True))
            if total_text_len > 0 and (form_text_len / total_text_len) > 0.5:
                logger.debug("Form wraps majority of page text (%d/%d chars). Unwrapping form.", form_text_len, total_text_len)
                form.unwrap()
            else:
                form.decompose()

    def _strip_generic_boilerplate(self, root: Tag) -> None:
        """Remove generic non-content tags and hidden elements inside the root."""
        # Generic non-content elements
        for tag_name in GENERIC_BOILERPLATE_TAGS:
            for element in list(root.find_all(tag_name)):
                if getattr(element, "attrs", None) is not None:
                    element.decompose()

        # Remove navigation, footer, or aside blocks accidentally nested inside root
        for tag_name in ["nav", "footer", "aside"]:
            for element in list(root.find_all(tag_name)):
                if getattr(element, "attrs", None) is not None:
                    element.decompose()

        # Remove hidden elements (CSS display:none or hidden attribute)
        for element in list(root.find_all(attrs={"hidden": True})):
            if getattr(element, "attrs", None) is not None:
                element.decompose()

        for element in list(root.find_all(style=re.compile(r"display\s*:\s*none", re.I))):
            if getattr(element, "attrs", None) is not None:
                element.decompose()

    def _clean_tables(self, root: Tag) -> None:
        """
        Normalize HTML tables for Markdown conversion.
        Uses a space separator when joining cell text to prevent word-gluing.
        Promotes first row to headers if <th> is missing.
        """
        for table in list(root.find_all("table")):
            rows = table.find_all("tr")
            if not rows:
                continue

            for cell in table.find_all(["th", "td"]):
                # Space-separated get_text prevents 'Duration3 Weeks' word-gluing
                cleaned_text = re.sub(r"\s+", " ", cell.get_text(" ", strip=True))
                cell.string = cleaned_text

            # Promote first row <td> to <th> if no headers exist
            if not table.find_all("th") and rows:
                first_row = rows[0]
                tds = first_row.find_all("td")
                if tds:
                    for td in tds:
                        td.name = "th"

    def _is_action_link(self, a: Tag) -> bool:
        """Check if an <a> tag points to a configured action path segment or action keyword."""
        href = (a.attrs.get("href") or "").strip()
        parsed = urlparse(href)
        path_segments = set(seg.lower() for seg in parsed.path.strip("/").split("/") if seg)

        # Match by exact path segment (e.g. /rfi/, /experience/, /write-review/)
        if path_segments & self.config.action_path_segments:
            return True

        # Match by explicit action keywords in query/path (e.g. 'quote')
        href_lower = href.lower()
        if any(kw in href_lower for kw in self.config.action_url_keywords):
            return True

        return False

    def _evaluate_removals_pass(self, root: Tag) -> Tuple[Set[Tag], List[str]]:
        """
        Pass 1: Read-only evaluation pass.
        Evaluates noise classes, anchor navigation, and multi-signal CTA blocks.
        Returns a set of tags to remove and a list of rules that fired.
        """
        to_remove: Set[Tag] = set()
        rules_fired: List[str] = []

        # 1. Site-specific noise classes
        for class_name in self.config.noise_classes:
            for element in root.find_all(class_=class_name):
                if getattr(element, "attrs", None) is not None:
                    to_remove.add(element)
                    rules_fired.append(f"noise_class:{class_name}")

        # 2. In-page anchor navigation rule (TOC jump chips)
        for container in root.find_all(["ul", "ol", "div"]):
            if getattr(container, "attrs", None) is None or container in to_remove:
                continue

            links = [a for a in container.find_all("a", href=True) if getattr(a, "attrs", None) is not None]
            if not links:
                continue

            anchor_links = [a for a in links if (a.attrs.get("href") or "").startswith("#")]
            anchor_ratio = len(anchor_links) / len(links)
            text_len = len(container.get_text(strip=True))

            # Must satisfy both: mostly anchor links AND low substantive text length
            if anchor_ratio >= self.config.anchor_nav_min_anchor_ratio and text_len < self.config.anchor_nav_max_chars:
                to_remove.add(container)
                rules_fired.append("anchor_nav_list")

        # 3. Multi-Signal CTA Removal Rule
        # Examine small cards, paragraphs, or blocks containing action links
        for a in list(root.find_all("a", href=True)):
            if getattr(a, "attrs", None) is None:
                continue

            if not self._is_action_link(a):
                continue

            # Locate the smallest block container enclosing this action link
            container = a.find_parent(["div", "p", "section"])
            if not container or getattr(container, "attrs", None) is None or container in to_remove:
                continue

            # NEVER delete the entire content root or primary speakable text
            container_classes = container.attrs.get("class", [])
            if container.name in ["main", "article"] or "speakable-text" in container_classes:
                to_remove.add(a)
                rules_fired.append("cta_standalone_link")
                continue

            # Calculate multi-signal metrics
            container_text = container.get_text(strip=True)
            char_count = len(container_text)

            has_table = bool(container.find("table"))
            is_whitelisted = any(kw in container_text.lower() for kw in self.config.whitelist_keywords)

            # ABSOLUTE KEEP RULES
            if has_table or is_whitelisted:
                to_remove.add(a)
                continue

            # MULTI-SIGNAL AGREEMENT: Must satisfy short + action link
            if char_count < self.config.cta_max_chars:
                to_remove.add(container)
                rules_fired.append("multi_signal_cta_card")
            else:
                # Ambiguous / longer text: only drop the action link itself, keep the container text!
                to_remove.add(a)
                rules_fired.append("flagged_cta_link_only")

        return to_remove, rules_fired

    def _execute_removals_pass(self, to_remove: Set[Tag]) -> None:
        """
        Pass 2: Decompose marked elements safely.
        """
        for element in to_remove:
            if getattr(element, "attrs", None) is not None and element.parent is not None:
                element.decompose()

    def _prune_orphan_headings(self, markdown_text: str) -> str:
        """
        Heuristic: Prune hollow/orphan headings (e.g. YouTube video shells).
        Only drop a heading if the next heading is at the SAME or HIGHER level (<= current_level),
        or nothing follows. If next heading is a child (next_level > current_level), it is kept.
        """
        lines = markdown_text.splitlines()
        cleaned_lines: List[str] = []

        for i, line in enumerate(lines):
            line_str = line.strip()
            heading_match = re.match(r"^(#{1,6})\s+", line_str)
            if heading_match:
                current_level = len(heading_match.group(1))

                # Look ahead for next substantive content
                next_content = ""
                next_heading_level = None
                for j in range(i + 1, min(i + 15, len(lines))):
                    candidate = lines[j].strip()
                    if candidate and candidate != "---":
                        next_content = candidate
                        next_h_match = re.match(r"^(#{1,6})\s+", candidate)
                        if next_h_match:
                            next_heading_level = len(next_h_match.group(1))
                        break

                # Drop only if nothing follows or next heading is at same/higher level
                if not next_content or (next_heading_level is not None and next_heading_level <= current_level):
                    logger.debug("Pruning orphan heading: %s", line_str)
                    continue

            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def clean_html(self, raw_html: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Clean raw HTML and convert to clean GitHub-Flavored Markdown.
        Uses lxml, root isolation, two-pass multi-signal scoring, and audit logging.
        """
        if not raw_html:
            return ""

        meta = metadata or {}
        page_title = meta.get("title", "Untitled Document")

        # Parse with lxml for C-speed and robust handling of malformed tags
        soup = BeautifulSoup(raw_html, "lxml")
        initial_chars = len(soup.get_text(strip=True))

        # 1. Pick content root first
        root = self._find_content_root(soup)

        # 2. Unwrap large forms or strip small interactive forms
        self._unwrap_or_strip_forms(root)

        # 3. Strip generic boilerplate (scripts, styles, hidden elements, nav/footer inside root)
        self._strip_generic_boilerplate(root)

        # 4. Clean tables with space-separated text to prevent word gluing
        self._clean_tables(root)

        # 5. Pass 1: Read-only evaluation of noise and multi-signal CTAs
        to_remove, rules_fired = self._evaluate_removals_pass(root)

        # 6. Pass 2: Execute removals
        self._execute_removals_pass(to_remove)

        # 7. Convert to Markdown using ATX headers and hyphen bullets
        markdown_body = markdownify.markdownify(
            str(root),
            heading_style="ATX",
            bullets="-",
            sub_symbol="",
            sup_symbol="",
        )

        # 8. Prune orphan/hollow headings
        markdown_body = self._prune_orphan_headings(markdown_body)

        # 9. Clean up excessive whitespace
        cleaned_markdown = re.sub(r"\n{3,}", "\n\n", markdown_body).strip()
        final_chars = len(cleaned_markdown)

        # 10. Audit Logging
        pct_kept = (final_chars / max(initial_chars, 1)) * 100
        logger.info(
            "Cleaned '%s': kept %.1f%% of text (%d -> %d chars) | Rules fired: %d",
            page_title,
            pct_kept,
            initial_chars,
            final_chars,
            len(rules_fired),
        )

        # 11. Prepend structured metadata header
        page_type = meta.get("page_type", "")
        source_url = meta.get("url", "")

        header_lines = []
        if page_title:
            header_lines.append(f"# {page_title}")
        if page_type:
            header_lines.append(f"**Page Type:** {page_type}")
        if source_url:
            header_lines.append(f"**Source URL:** {source_url}")

        if header_lines:
            header_block = "\n".join(header_lines) + "\n\n---\n\n"
            return header_block + cleaned_markdown

        return cleaned_markdown
