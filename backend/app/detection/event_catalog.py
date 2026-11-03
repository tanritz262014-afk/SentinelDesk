"""Windows Event IDs that SentinelDesk understands.

Each known Event ID gets a category (used for dashboard charts) and a short
plain-English description. Unknown Event IDs are still accepted and stored
with the category "Other".
"""

EVENT_CATALOG: dict[int, dict[str, str]] = {
    4624: {
        "category": "Authentication Success",
        "description": "An account successfully logged on",
    },
    4625: {
        "category": "Authentication Failure",
        "description": "An account failed to log on",
    },
    4720: {
        "category": "Account Management",
        "description": "A user account was created",
    },
    7045: {
        "category": "Service Installation",
        "description": "A new service was installed in the system",
    },
}

OTHER_CATEGORY = "Other"


def get_category(event_id: int) -> str:
    return EVENT_CATALOG.get(event_id, {}).get("category", OTHER_CATEGORY)


def get_description(event_id: int) -> str:
    return EVENT_CATALOG.get(event_id, {}).get("description", f"Windows event {event_id}")
