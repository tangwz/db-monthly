#!/usr/bin/env python3
"""
Fetch latest posts from https://mysql.taobao.org/monthly/ (or a mirror) and
update README.md with new entries grouped by database categories. The script
parses month pages and appends unseen articles to the corresponding sections in
README.md. If the default site is unreachable, set the ``MONTHLY_BASE_URL``
environment variable to point to an accessible mirror.
"""
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from html.parser import HTMLParser
import urllib.request

BASE_URL = os.environ.get("MONTHLY_BASE_URL", "https://mysql.taobao.org/monthly")


def fetch(url: str) -> str:
    """Fetch URL and return decoded text."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    proxy = os.environ.get("MONTHLY_PROXY")
    if proxy:
        handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
    else:
        handler = urllib.request.ProxyHandler({})  # disable env proxies
    opener = urllib.request.build_opener(handler)
    try:
        with opener.open(req, timeout=10) as resp:  # pragma: no cover - network I/O
            return resp.read().decode("utf-8", errors="ignore")
    except Exception as exc:  # pragma: no cover - network I/O
        raise RuntimeError(f"failed to fetch {url}: {exc}")


def get_months(html: str):
    """Extract all (year, month) tuples from index html."""
    pattern = re.compile(r"/monthly/(\d{4})/(\d{2})/")
    months = {(int(y), int(m)) for y, m in pattern.findall(html)}
    return sorted(months)


class MonthParser(HTMLParser):
    """Parse monthly page into articles grouped by category."""

    def __init__(self):
        super().__init__()
        self.category = None
        self.in_h2 = False
        self.in_li = False
        self.link = None
        self.text_parts = []
        self.articles = defaultdict(list)

    def handle_starttag(self, tag, attrs):
        if tag == "h2":
            self.in_h2 = True
        elif tag == "li":
            self.in_li = True
            self.link = None
            self.text_parts = []
        elif tag == "a" and self.in_li:
            attrs = dict(attrs)
            self.link = attrs.get("href")

    def handle_endtag(self, tag):
        if tag == "h2":
            self.in_h2 = False
        elif tag == "li":
            if self.category and self.link and self.text_parts:
                text = "".join(self.text_parts).strip()
                m = re.match(r"\[(.*?)\]\s*(.*)", text)
                if m:
                    typ, title = m.groups()
                else:
                    parts = text.split(None, 1)
                    typ = parts[0] if len(parts) == 2 else ""
                    title = parts[-1]
                self.articles[self.category].append((typ, title, self.link))
            self.in_li = False
            self.link = None
            self.text_parts = []

    def handle_data(self, data):
        if self.in_h2:
            self.category = data.strip()
        elif self.in_li:
            self.text_parts.append(data)


def parse_month(year: int, month: int):
    html = fetch(f"{BASE_URL}/{year:04d}/{month:02d}/")
    parser = MonthParser()
    parser.feed(html)
    return parser.articles


def update_readme(new_articles):
    readme_path = Path(__file__).resolve().parent.parent / "README.md"
    content = readme_path.read_text(encoding="utf-8")

    for category, items in new_articles.items():
        if not items:
            continue
        table_header = f"# {category}\n| 分类 | 标题  |\n|---|---|"
        if table_header not in content:
            # skip categories not present
            continue
        lines = [f"| {typ} | [{title}]({link}) |" for typ, title, link in items]
        content = content.replace(table_header, table_header + "\n" + "\n".join(lines))

    readme_path.write_text(content, encoding="utf-8")


def main():  # pragma: no cover - integration logic
    index_html = fetch(BASE_URL + "/")
    months = get_months(index_html)
    readme = Path(__file__).resolve().parent.parent / "README.md"
    existing = readme.read_text(encoding="utf-8")

    updates = defaultdict(list)
    for y, m in months:
        url = f"{BASE_URL}/{y:04d}/{m:02d}/"
        if url in existing:
            continue
        try:
            articles = parse_month(y, m)
        except Exception as exc:
            print(f"Failed to fetch {y}-{m:02d}: {exc}", file=sys.stderr)
            continue
        for cat, items in articles.items():
            updates[cat].extend(items)

    if updates:
        update_readme(updates)


if __name__ == "__main__":
    main()
