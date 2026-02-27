"""
Team Configuration Template — RFP Scraper

Copy this file to team_config.py and fill in your team members:
    cp team_config.template.py team_config.py

Each member entry needs:
  - name:     Display name (used in email greetings)
  - email:    Recipient address for Monday digest
  - patterns: List of keyword phrases to match against RFP titles,
              descriptions, and agency names (case-insensitive)
"""

TEAM_MEMBERS = [
    {
        "name": "Jane Doe",
        "email": "jdoe@university.edu",
        "patterns": [
            "economic development", "fiscal analysis",
            "cost-benefit", "impact study",
        ],
    },
    # Add more team members here...
]
