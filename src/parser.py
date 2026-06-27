import os
import re

from src.config import PKA_REPO_PATH

LIST_FOLDER_MAP = {
    "topics":   "PKM/My Life/Topics",
    "projects": "PKM/My Life/Projects",
    "goals":    "PKM/My Life/Goals",
    "crm":      "PKM/CRM/People",
    "incoming": "PKM/Journal",
    "research": "PKM/My Life/Topics",
}


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


def _frontmatter(card, list_name, date_str):
    name = card["name"]
    url = card["url"]
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
        research_url = _extract_url(card)
        url_line = f"research_url: {research_url}\n" if research_url else ""
        return (
            f"---\nname: {name}\nsource_url: {url}\ndate: {date_str}\n"
            f"{url_line}tags:\n  - research\nresearch_status: pending\n---"
        )
    raise ValueError(f"Unknown list_name: {list_name}")


def _extract_url(card):
    """Return the first non-Trello URL from desc or attachments, or None."""
    for text in [card.get("desc", ""), *[a["url"] for a in card.get("attachments", [])]]:
        for match in re.finditer(r'https?://[^\s\)\]"]+', text):
            u = match.group(0).rstrip(".,")
            if "trello.com" not in u:
                return u
    return None


def _body(card):
    parts = []
    if card.get("desc", "").strip():
        parts.append(card["desc"].strip())
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
