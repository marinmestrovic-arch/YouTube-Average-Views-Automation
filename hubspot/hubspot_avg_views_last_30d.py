#!/usr/bin/env python3
"""
Update HubSpot contact properties:
- youtube_video_average_views
- last_updated_youtube_video_average_views

For contacts whose (last_updated_youtube_video_average_views) is > 30 days ago
(or missing), compute the current 30-day average views for videos longer than
X minutes on their YouTube channel.

Requirements:
    - env HUBSPOT_PRIVATE_APP_TOKEN
    - env YT_API_KEY (or pass into YouTubeClient some other way)

Assumptions:
    - Contact has a text property: youtube_channel_identifier
      which can be a handle (@...), channel URL, or channel ID.

Properties (internal names):
    - youtube_video_average_views (number)
    - last_updated_youtube_video_average_views (datetime or date)
"""

import os
import sys
import warnings
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

import requests
from dateutil import parser as date_parser

warnings.filterwarnings("ignore", category=Warning, module="urllib3")

# Make project root importable, same pattern as your existing script
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.youtube_api.client import YouTubeClient
from scripts.avg_views_last_30d import avg_views_last_30d  # reuse your function


# ---------------------------
# Config / constants
# ---------------------------

HUBSPOT_TOKEN = os.environ.get("HUBSPOT_PRIVATE_APP_TOKEN")
if not HUBSPOT_TOKEN:
    raise RuntimeError("HUBSPOT_PRIVATE_APP_TOKEN env var is required")

BASE_URL = "https://api.hubapi.com"

HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_TOKEN}",
    "Content-Type": "application/json",
}

# How many days before we consider data "stale"
STALE_DAYS = int(os.environ.get("YOUTUBE_AVG_STALE_DAYS", "30"))

# Optional tuning
MIN_DURATION_MINUTES = int(os.environ.get("YOUTUBE_MIN_DURATION_MINUTES", "3"))
FETCH_COUNT = int(os.environ.get("YOUTUBE_FETCH_COUNT", "50"))

# HubSpot property internal names
PROP_AVG_VIEWS = "youtube_video_average_views"
PROP_LAST_UPDATED = "last_updated_youtube_video_average_views"
PROP_CHANNEL_IDENTIFIER = "youtube_handle"


# ---------------------------
# Helpers
# ---------------------------

def iso_today_midnight_utc() -> str:
    """Return ISO8601 at midnight UTC (HubSpot-friendly date/datetime)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")


def is_stale_or_missing(iso_value: Optional[str]) -> bool:
    """Return True if date is missing or older than STALE_DAYS."""
    if not iso_value:
        return True
    try:
        dt = date_parser.parse(iso_value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except Exception:
        return True
    cutoff = datetime.now(timezone.utc) - timedelta(days=STALE_DAYS)
    return dt < cutoff


# ---------------------------
# HubSpot API calls
# ---------------------------

def search_contacts_needing_update(limit: int = 200) -> List[Dict[str, Any]]:
    """Fetch contacts with channel identifier and filter stale/missing dates in-code."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=STALE_DAYS)
    contacts: Dict[str, Dict[str, Any]] = {}

    url = f"{BASE_URL}/crm/v3/objects/contacts/search"
    after = None
    while len(contacts) < limit:
        payload: Dict[str, Any] = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": PROP_CHANNEL_IDENTIFIER,
                            "operator": "HAS_PROPERTY",
                        }
                    ]
                }
            ],
            "properties": [
                PROP_AVG_VIEWS,
                PROP_LAST_UPDATED,
                PROP_CHANNEL_IDENTIFIER,
                "firstname",
                "lastname",
                "email",
            ],
            "limit": min(1000, limit - len(contacts)),
        }
        if after:
            payload["after"] = after
        resp = requests.post(url, headers=HEADERS, json=payload, timeout=20)
        try:
            resp.raise_for_status()
        except requests.HTTPError:
            print(f"[hubspot debug] search failed {resp.status_code}")
            try:
                print(f"[hubspot debug] response: {resp.json()}")
            except Exception:
                print(f"[hubspot debug] response (text): {resp.text}")
            print(f"[hubspot debug] request payload: {payload}")
            raise
        data = resp.json()
        for c in data.get("results", []):
            props = c.get("properties", {}) or {}
            last_updated = props.get(PROP_LAST_UPDATED)
            if not is_stale_or_missing(last_updated):
                continue
            contacts[c["id"]] = c
        after = data.get("paging", {}).get("next", {}).get("after")
        if not after or len(contacts) >= limit:
            break

    return list(contacts.values())


def update_contact_properties(contact_id: str, properties: Dict[str, Any]) -> None:
    """PATCH /crm/v3/objects/contacts/{contactId}"""
    url = f"{BASE_URL}/crm/v3/objects/contacts/{contact_id}"
    payload = {"properties": properties}
    resp = requests.patch(url, headers=HEADERS, json=payload, timeout=20)
    resp.raise_for_status()


# ---------------------------
# Main logic
# ---------------------------

def process_contact(contact: Dict[str, Any], yt_client: YouTubeClient) -> None:
    cid = contact["id"]
    props = contact.get("properties", {}) or {}

    # Get channel identifier from contact
    channel_identifier = props.get(PROP_CHANNEL_IDENTIFIER)
    if not channel_identifier:
        print(f"[skip] contact {cid}: no {PROP_CHANNEL_IDENTIFIER}")
        return
    print(
        f"[debug] contact {cid} email={props.get('email')} "
        f"{PROP_CHANNEL_IDENTIFIER}='{channel_identifier}' "
        f"last_updated='{props.get(PROP_LAST_UPDATED)}'"
    )

    # Compute new average using your existing helper
    try:
        avg = avg_views_last_30d(
            yt_client,
            channel_identifier=channel_identifier,
            min_minutes=MIN_DURATION_MINUTES,
            fetch_count=FETCH_COUNT,
        )
    except Exception as e:
        extra = ""
        resp = getattr(e, "response", None)
        if resp is not None:
            try:
                extra = f" | youtube_error={resp.json()}"
            except Exception:
                extra = f" | youtube_error_text={resp.text}"
        print(
            f"[error] contact {cid}: failed to compute avg for '{channel_identifier}': {e}{extra}"
        )
        return

    # Prepare update
    avg_rounded = round(avg / 100) * 100
    update_props = {
        PROP_AVG_VIEWS: f"{avg_rounded:.0f}",  # HubSpot number can be passed as string
        PROP_LAST_UPDATED: iso_today_midnight_utc(),
    }

    try:
        update_contact_properties(cid, update_props)
        print(
            f"[ok] contact {cid} ({props.get('email')}) "
            f"channel='{channel_identifier}' avg={avg_rounded:.0f}"
        )
    except Exception as e:
        print(f"[error] contact {cid}: failed to update HubSpot: {e}")


def main() -> None:
    yt_client = YouTubeClient()  # uses YT_API_KEY env var internally

    contacts = search_contacts_needing_update(limit=200)
    print(f"Found {len(contacts)} contact(s) needing update")

    for c in contacts:
        last_updated = (c.get("properties") or {}).get(PROP_LAST_UPDATED)
        if not is_stale_or_missing(last_updated):
            # If search conditions change, this extra safety ensures correctness
            continue
        process_contact(c, yt_client)


if __name__ == "__main__":
    main()
