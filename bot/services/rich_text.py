"""Formatted announcement text from the Mini App editor → the HTML subset Telegram accepts.

The browser sends whatever its editor produced; only Telegram's tags survive (with
attributes dropped except a safe link href), everything else becomes plain text.
"""
import html
import re
from html.parser import HTMLParser

# editor tag -> Telegram tag
TAGS = {
    "b": "b", "strong": "b", "i": "i", "em": "i", "u": "u", "ins": "u",
    "s": "s", "strike": "s", "del": "s", "blockquote": "blockquote",
    "tg-spoiler": "tg-spoiler", "code": "code", "a": "a",
}
SAFE_HREF = re.compile(r"^(https?://|tg://)[^\s\"'<>]+$", re.IGNORECASE)


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.html: list[str] = []
        self.plain: list[str] = []
        self.open: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            self.html.append("\n")
            self.plain.append("\n")
            return
        mapped = TAGS.get(tag)
        if mapped is None or mapped in self.open:
            return  # unknown tag, or the same style nested in itself
        if mapped == "a":
            href = dict(attrs).get("href") or ""
            if not SAFE_HREF.match(href):
                return
            self.html.append(f'<a href="{html.escape(href, quote=True)}">')
        else:
            self.html.append(f"<{mapped}>")
        self.open.append(mapped)

    def handle_endtag(self, tag):
        mapped = TAGS.get(tag)
        if mapped in self.open:
            # Close everything opened inside it too, keeping the tags properly nested.
            while self.open:
                inner = self.open.pop()
                self.html.append(f"</{inner}>")
                if inner == mapped:
                    break

    def handle_data(self, data):
        self.html.append(html.escape(data, quote=False))
        self.plain.append(data)

    def result(self) -> tuple[str, str]:
        while self.open:
            self.html.append(f"</{self.open.pop()}>")
        return "".join(self.html).strip(), "".join(self.plain).strip()


def to_telegram_html(raw: str) -> tuple[str, str]:
    """Returns (Telegram HTML, plain text). The plain text is what counts for the caption limit."""
    parser = _Sanitizer()
    parser.feed(raw or "")
    parser.close()
    return parser.result()
