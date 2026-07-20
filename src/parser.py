import os
import re

import yaml

from src.config import PKA_REPO_PATH

LIST_FOLDER_MAP = {
    "topics":   "PKM/My Life/Topics",
    "projects": "PKM/My Life/Projects",
    "goals":    "PKM/My Life/Goals",
    "crm":      "PKM/CRM/People",
    "incoming": "PKM/Journal",
    "research": "PKM/My Life/Topics",
}

# --- Research list: "fetch a URL" vs "review the pasted body" -------------
#
# A Research card's *source_url* is always the Trello permalink (origin
# tracking — never a fetch target). Whether there is a genuine external
# resource to fetch is decided separately and recorded as `research_mode`:
#
#   research_mode: fetch  -> `research_url` is set; pax-vm fetches THAT url.
#   research_mode: body   -> no reliable single external target; pax-vm
#                            summarizes/reviews the note body directly.
#
# Decision precedence:
#   1. Explicit Trello label override, if present (case-insensitive).
#   2. Heuristic: exactly one non-Trello URL found across the card's name,
#      description and attachments, AND the surrounding text (name+desc
#      minus that URL) is short -> the URL IS the point of the card ("go
#      check this out"). Otherwise any URL present is assumed to be
#      *mentioned in passing* inside a longer pasted body, not a fetch
#      target (e.g. a product name cited inside 5 paragraphs of prompts).
RESEARCH_FETCH_LABELS = {"research-fetch", "fetch"}
RESEARCH_BODY_LABELS = {"research-body", "research-no-fetch", "no-fetch", "body"}
RESEARCH_SHORT_REMAINDER_CHARS = 200  # "just a link (+ short caption)" cutoff


def slugify(name):
    s = name.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "untitled"


def unique_path(folder, filename):
    path = os.path.join(folder, filename)
    if not os.path.exists(path):
        return path
    stem = filename[:-3]
    counter = 2
    while True:
        candidate = os.path.join(folder, f"{stem}-{counter}.md")
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def _date(iso_str):
    return iso_str[:10]


def _yaml_scalar(value: str) -> str:
    """Return `value` as a YAML-safe plain/quoted scalar (single line, no
    document-end markers). Trello card names are free text and can contain
    a trailing colon, quotes, or other characters that break a naive
    f-string-interpolated frontmatter block (a card literally titled
    "check these prompts list and comment:" produced invalid YAML — the
    trailing colon read as a nested mapping key). Every free-text field
    goes through this before landing in the frontmatter string.
    """
    dumped = yaml.safe_dump(value, allow_unicode=True, default_flow_style=True, width=1 << 31).strip()
    if dumped.endswith("..."):
        dumped = dumped[:-3].rstrip()
    return dumped


def _frontmatter(card, list_name, date_str):
    name = _yaml_scalar(card["name"])
    url = _yaml_scalar(card["url"])
    if list_name == "topics":
        return f"---\nname: {name}\nsource_url: {url}\ndate: {date_str}\n---"
    if list_name == "projects":
        return f"---\nname: {name}\nstatus: active\nsource_url: {url}\ndate: {date_str}\n---"
    if list_name == "goals":
        return f"---\nname: {name}\nsource_url: {url}\ndate: {date_str}\n---"
    if list_name == "crm":
        return f"---\nfull_name: {name}\nsource_url: {url}\ndate: {date_str}\n---"
    if list_name == "incoming":
        return f"---\ndate: {date_str}\nsource: trello\nsource_url: {url}\ntags:\n  - inbox\n---"
    if list_name == "research":
        mode, research_url = _research_mode_and_url(card)
        research_url_line = f"research_url: {_yaml_scalar(research_url)}\n" if research_url else ""
        return (
            f"---\nname: {name}\nsource_url: {url}\ndate: {date_str}\n"
            f"{research_url_line}research_mode: {mode}\n"
            f"tags:\n  - research\nresearch_status: pending\n---"
        )
    raise ValueError(f"Unknown list_name: {list_name}")


def _extract_all_urls(card):
    """Return an ordered list of distinct non-Trello URLs found anywhere in
    the card's name, description, or attachments.

    Card *name* is included deliberately: cards are sometimes titled with the
    bare URL and left with an empty description (e.g. a card literally named
    "https://github.com/org/repo"), so scanning desc alone misses them.
    """
    seen = []
    texts = [card.get("name", ""), card.get("desc", ""),
             *[a["url"] for a in card.get("attachments", [])]]
    for text in texts:
        for match in re.finditer(r'https?://[^\s\)\]"]+', text):
            u = match.group(0).rstrip(".,")
            if "trello.com" in u:
                continue
            if u not in seen:
                seen.append(u)
    return seen


def _extract_url(card):
    """Return the first non-Trello URL found (name, desc, or attachments), or None."""
    urls = _extract_all_urls(card)
    return urls[0] if urls else None


def _research_mode_and_url(card):
    """Decide fetch-vs-body mode and the research_url (if any) for a Research card.

    Returns (mode, research_url) where mode is "fetch" or "body" and
    research_url is a string or None.
    """
    labels = {lbl.lower() for lbl in card.get("labels", [])}
    if labels & RESEARCH_FETCH_LABELS:
        return "fetch", _extract_url(card)
    if labels & RESEARCH_BODY_LABELS:
        return "body", None

    urls = _extract_all_urls(card)
    if len(urls) == 1:
        remainder = f"{card.get('name', '')}\n{card.get('desc', '')}".replace(urls[0], "").strip()
        if len(remainder) <= RESEARCH_SHORT_REMAINDER_CHARS:
            return "fetch", urls[0]
    return "body", None


def _checklists(card):
    """Render a card's Trello Checklists as markdown task-list sections.

    Each checklist becomes a section headed by its name; each item becomes a
    GitHub-style task-list line — `- [x] item` when the item is complete on the
    card, `- [ ] item` when it is not — preserving the subtask structure written
    on the card. Empty checklists (no items) are skipped so they leave no
    dangling heading. Returns a list of section strings (one per non-empty
    checklist); [] when the card has no checklists.
    """
    sections = []
    for checklist in card.get("checklists", []):
        items = checklist.get("items", [])
        if not items:
            continue
        name = checklist.get("name") or "Checklist"
        lines = "\n".join(
            f"- [{'x' if item.get('checked') else ' '}] {item.get('name', '')}"
            for item in items
        )
        sections.append(f"## {name}\n\n{lines}")
    return sections


def _body(card):
    parts = []
    if card.get("desc", "").strip():
        parts.append(card["desc"].strip())
    parts.extend(_checklists(card))
    if card.get("attachments"):
        refs = "\n".join(f"- [{a['name'] or a['url']}]({a['url']})" for a in card["attachments"])
        parts.append(f"## References\n\n{refs}")
    return "\n\n".join(parts)


def parse_card(card):
    """Return (target_path, frontmatter_str, body_str) for a card dict."""
    list_name = card["list_name"]
    date_str = _date(card["date_modified"])
    base = LIST_FOLDER_MAP[list_name]

    if list_name == "incoming":
        yyyy, mm = date_str[:4], date_str[5:7]
        folder = os.path.join(PKA_REPO_PATH, base, yyyy, mm)
        slug = slugify(card["name"])
        filename = f"{date_str}-{slug}.md"
    else:
        folder = os.path.join(PKA_REPO_PATH, base)
        filename = f"{slugify(card['name'])}.md"

    body = _body(card)
    if list_name == "research":
        suffix = "## Pax Research\n\n_Pending..._"
        body = f"{body}\n\n{suffix}" if body else suffix
    return unique_path(folder, filename), _frontmatter(card, list_name, date_str), body
