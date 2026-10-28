"""
Site-specific extraction and cleaning configuration for PlacidWay.
Decouples domain knowledge (classes, action paths, whitelists, thresholds)
from the generic DOMCleaner engine.
"""

from dataclasses import dataclass, field
from typing import Set, List


@dataclass(frozen=True)
class SiteCleanerConfig:
    """
    Configuration contract for site-specific DOM cleaning and extraction rules.
    """
    site_name: str = "placidway"
    
    # Sitewide container classes representing non-content carousels, popups, and widgets
    noise_classes: List[str] = field(default_factory=lambda: [
        "related-centers-sec",
        "related-packages-sec",
        "related-experiences-sec",
        "related-videos-sec",
        "related-widgets-row",
        "related-cards-slider",
        "dt-logos-widget",
        "dt-pages-bottom-widget",
        "logos-widget-sec",
        "pw-accreditations",
        "pw-stats-section",
        "pw-footer__network",
        "pw-footer__wrap",
        "cta-form-container",
        "sidebar-form",
        "chatbot-popup",
        "ctm-chatbot-widget",
        "ai-search-popup",
        "modal",
        "modal-backdrop",
        "splide",
        "splide__track",
        "splide__list",
        "image-banner-slider",
        "thumnbails-slider",
        "both-sliders-container",
        "social-popup-main",
        "request-vido-popup-main",
        "social-icon",
    ])
    
    # URL path segments identifying transactional action endpoints (matched by path segment, not substring)
    action_path_segments: Set[str] = field(default_factory=lambda: {
        "rfi",
        "write-review",
        "experience",
    })
    
    # Action keywords in links indicating promotional CTAs
    action_url_keywords: Set[str] = field(default_factory=lambda: {
        "quote",
        "free-quote",
    })
    
    # Protected content keywords (sections containing these are protected from removal)
    whitelist_keywords: Set[str] = field(default_factory=lambda: {
        "doctor",
        "dr.",
        "bautista",
        "physician",
        "oncology",
        "pricing",
        "price",
        "cost",
        "faq",
        "included",
        "inclusions",
        "excluded",
        "exclusions",
        "itinerary",
        "out-patient",
        "in-patient",
        "accreditation",
        "qualification",
        "certification",
        "award",
        "testimonial",
    })
    
    # Multi-signal CTA thresholds
    cta_max_chars: int = 350
    cta_min_link_density: float = 0.35
    
    # In-page anchor navigation thresholds
    anchor_nav_max_chars: int = 300
    anchor_nav_min_anchor_ratio: float = 0.80


PLACIDWAY_CONFIG = SiteCleanerConfig()
