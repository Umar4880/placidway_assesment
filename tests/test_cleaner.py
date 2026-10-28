"""
Unit tests for DOMCleaner (FR-2: Surgical DOM Cleaning & Table Preservation).
"""

from pathlib import Path
import pytest
from src.ingestion.cleaner import DOMCleaner
from src.ingestion.urls import AUTHORIZED_URLS


def test_cleaner_page_2_preserves_pricing_table_and_inclusions():
    cleaner = DOMCleaner()
    page_files = list(Path("data/raw_html").glob("page_2_*.html"))
    assert page_files, "page_2 raw HTML must exist in data/raw_html/"

    raw_html = page_files[0].read_text(encoding="utf-8")
    meta = AUTHORIZED_URLS[1]  # Page 2 metadata
    md = cleaner.clean_html(raw_html, meta)

    # 1. Header context injected
    assert "# Alternative Adenocarcinoma Cancer Treatment Package" in md
    assert "**Page Type:** Treatment Package" in md
    assert "**Source URL:**" in md

    # 2. Pricing table preserved
    assert "| Out-Patient Program | 3 Weeks | $18,995 |" in md or "18,995" in md
    assert "30,000" in md

    # 3. Inclusion and exclusion headers preserved
    assert "Included in the Out-Patient Program" in md
    assert "Included in the In-Patient Program" in md
    assert "Optional Specialized Procedures" in md
    assert "Excluded Services and Contingency Costs" in md

    # 4. Sitewide cross-sell carousel noise stripped
    assert "Unlock the Best Cancer Treatment Packages" not in md
    assert "Cancer Treatment Solutions Near You" not in md
    assert "Transformative Cancer Treatment Experiences" not in md
    assert "Related Experiences:" not in md


def test_cleaner_page_6_preserves_pricing_table():
    cleaner = DOMCleaner()
    page_files = list(Path("data/raw_html").glob("page_6_*.html"))
    assert page_files, "page_6 raw HTML must exist"

    raw_html = page_files[0].read_text(encoding="utf-8")
    meta = AUTHORIZED_URLS[5]
    md = cleaner.clean_html(raw_html, meta)

    assert "18995" in md or "$18995" in md
    assert "Breast Cancer" in md
    assert "Prostate Cancer" in md
    assert "Lung Cancer" in md


def test_cleaner_page_7_preserves_cost_tables():
    cleaner = DOMCleaner()
    page_files = list(Path("data/raw_html").glob("page_7_*.html"))
    assert page_files, "page_7 raw HTML must exist"

    raw_html = page_files[0].read_text(encoding="utf-8")
    meta = AUTHORIZED_URLS[6]
    md = cleaner.clean_html(raw_html, meta)

    assert "Acupuncture Therapy Package" in md
    assert "Ayurvedic Panchakarma" in md
    assert "Alternative Stem Cell Therapy" in md


def test_cleaner_page_1_preserves_doctors_and_strips_consultation_cta():
    cleaner = DOMCleaner()
    page_files = list(Path("data/raw_html").glob("page_1_*.html"))
    assert page_files, "page_1 raw HTML must exist"

    raw_html = page_files[0].read_text(encoding="utf-8")
    meta = AUTHORIZED_URLS[0]
    md = cleaner.clean_html(raw_html, meta)

    # 1. Doctors must be preserved
    assert "Dr. Carlos Bautista" in md
    assert "Dr. David Alvarez" in md
    assert "Dr. Adolfo Carrillo" in md
    assert "Dr. Pablo Orozco" in md

    # 2. Consultation CTA box must be cleanly removed
    assert "Request a Consultation" not in md


def test_cleaner_handles_malformed_html():
    """Verify lxml safely fixes unclosed containers and nested markup."""
    cleaner = DOMCleaner()
    malformed_html = """
    <main>
        <div>
            <h2>Clinical Protocol
            <p>Unclosed paragraph with <b>bold text that does not close
        </div>
        <div class="cta-box">
            <a href="https://www.placidway.com/rfi/5/Alternative-Cancer-Treatment">Contact Us</a>
        </div>
    </main>
    """
    md = cleaner.clean_html(malformed_html, {"title": "Malformed Test"})
    assert "Clinical Protocol" in md
    assert "Contact Us" not in md

