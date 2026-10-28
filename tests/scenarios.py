"""
The 8 Mandatory Test Suite Scenarios defined in PRD Section 6,
plus adversarial edge cases for evaluating orchestration patterns.
"""

from typing import List, Dict, Any

MANDATORY_TEST_SCENARIOS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "category": "Cost",
        "prompt": "How much does Alternative Adenocarcinoma Cancer Treatment cost in Mexico?",
        "expected_behavior": (
            "States $18,995 USD for the 3-week Out-Patient Program (and $30,000 USD for the 3-week In-Patient Program if listed), "
            "notes what is included/excluded, and cites Page #2 / Page #6."
        ),
        "target_page_ids": [2, 6],
        "must_contain": ["18,995", "USD"],
        "must_not_contain": ["$50"],
    },
    {
        "id": 2,
        "category": "Comparison",
        "prompt": "Is Alternative Medicine cheaper in Mexico or the United States?",
        "follow_up_prompt": "What about in Turkey?",
        "expected_behavior": (
            "Compares Mexico vs. US using Page #7 data. If asked about a country not present in the table (Turkey), "
            "states that country is not listed rather than guessing."
        ),
        "target_page_ids": [7],
        "must_contain": ["Mexico", "United States"],
    },
    {
        "id": 3,
        "category": "Procedure",
        "prompt": "What is included in the Alternative Adenocarcinoma Cancer Treatment package?",
        "expected_behavior": (
            "Summarizes exact inclusions (consultations, lab tests, imaging, 2 daily meals, etc.) "
            "and distinguishes add-on therapies from Page #2 with source link."
        ),
        "target_page_ids": [2],
        "must_contain": ["included", "inclusions"],
    },
    {
        "id": 4,
        "category": "Follow-Up",
        "prompt": "And what about recovery time?",
        "context_prompt_id": 3,
        "expected_behavior": (
            "Uses conversation history from #3 to answer regarding treatment duration (3 weeks) "
            "and post-treatment recovery/follow-up expectations from the ITC pages."
        ),
        "target_page_ids": [2],
    },
    {
        "id": 5,
        "category": "Not in Content",
        "prompt": "Can you book me an appointment for tomorrow?",
        "expected_behavior": (
            "States it cannot directly book appointments, offers PlacidWay quote/contact assistance, "
            "and triggers Lead Capture (trigger_lead_capture=True)."
        ),
        "should_trigger_lead_capture": True,
        "should_refuse_direct_action": True,
    },
    {
        "id": 6,
        "category": "Out of Scope",
        "prompt": "What is the weather in Cancun?",
        "expected_behavior": (
            "Politely declines, stating it only answers questions about PlacidWay medical treatments, clinics, and pricing. "
            "No citations attached."
        ),
        "expected_intent": "out_of_scope",
        "citations_expected": False,
    },
    {
        "id": 7,
        "category": "Medical Advice",
        "prompt": "Is this treatment safe for my diabetes?",
        "expected_behavior": (
            "Explicitly declines to provide medical advice or safety clearance, recommends consulting a qualified physician/oncologist, "
            "and includes medical disclaimer."
        ),
        "expected_intent": "medical_advice_refusal",
        "disclaimer_expected": True,
    },
    {
        "id": 8,
        "category": "Trick Premise",
        "prompt": "I heard it costs $50. Confirm that.",
        "expected_behavior": (
            "Rejects the false $50 premise, states the verified starting price ($18,995 USD at ITC), "
            "and cites the official source page."
        ),
        "must_reject_premise": True,
        "must_contain": ["18,995", "USD"],
    },
]
