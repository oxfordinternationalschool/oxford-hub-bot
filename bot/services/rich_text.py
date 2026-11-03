"""Formatted announcement text from the Mini App editor → the HTML subset Telegram accepts.

The browser sends whatever its editor produced; only Telegram's tags survive (with
attributes dropped except a safe link href), everything else becomes plain text.
"""
import html
import re
from html.parser import HTMLParser

from aiogram.types import (
    InputRichBlockBlockQuotation, InputRichBlockList, InputRichBlockListItem, InputRichBlockParagraph,
    RichTextBold, RichTextCode, RichTextItalic, RichTextSpoiler, RichTextStrikethrough, RichTextUnderline, RichTextUrl,
)

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


# ---------- Telegram HTML -> rich message blocks (for slideshow/collage announcements) ----------

class _Runs(HTMLParser):
    """Flattens sanitized Telegram HTML into styled text runs, keeping blockquotes apart."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.styles: list[str] = []
        self.url: str | None = None
        self.sections: list[tuple[bool, list]] = [(False, [])]  # (is_quote, runs)

    def handle_starttag(self, tag, attrs):
        if tag == "blockquote":
            self.sections.append((True, []))
        elif tag == "a":
            self.url = dict(attrs).get("href")
        else:
            self.styles.append(tag)

    def handle_endtag(self, tag):
        if tag == "blockquote":
            self.sections.append((False, []))
        elif tag == "a":
            self.url = None
        elif tag in self.styles:
            self.styles.remove(tag)

    def handle_data(self, data):
        self.sections[-1][1].append((data, tuple(self.styles), self.url))


_RICH_STYLE = {
    "b": RichTextBold, "i": RichTextItalic, "u": RichTextUnderline, "s": RichTextStrikethrough,
    "tg-spoiler": RichTextSpoiler, "code": RichTextCode,
}


def _rich_text(runs: list):
    parts = []
    for text, styles, url in runs:
        piece = text
        for style in reversed(styles):
            piece = _RICH_STYLE[style](text=piece)
        if url:
            piece = RichTextUrl(text=piece, url=url)
        parts.append(piece)
    return parts[0] if len(parts) == 1 else parts


def _lines(runs: list) -> list[list]:
    lines: list[list] = [[]]
    for text, styles, url in runs:
        for i, chunk in enumerate(text.split("\n")):
            if i:
                lines.append([])
            if chunk:
                lines[-1].append((chunk, styles, url))
    return [line for line in lines if "".join(t for t, _, _ in line).strip()]


def _paragraphs(runs: list) -> list:
    """Lines become paragraphs; consecutive "• " lines become one bulleted list."""
    blocks: list = []
    bullets: list = []
    for line in _lines(runs):
        first_text = line[0][0]
        if first_text.startswith("• "):
            line = [(first_text[2:], *line[0][1:])] + line[1:]
            bullets.append(InputRichBlockListItem(blocks=[InputRichBlockParagraph(text=_rich_text(line))]))
            continue
        if bullets:
            blocks.append(InputRichBlockList(items=bullets))
            bullets = []
        blocks.append(InputRichBlockParagraph(text=_rich_text(line)))
    if bullets:
        blocks.append(InputRichBlockList(items=bullets))
    return blocks


def to_rich_blocks(telegram_html: str) -> list:
    """Sanitized Telegram HTML (from to_telegram_html) as rich message blocks."""
    parser = _Runs()
    parser.feed(telegram_html or "")
    parser.close()
    blocks: list = []
    for is_quote, runs in parser.sections:
        inner = _paragraphs(runs)
        if is_quote and inner:
            blocks.append(InputRichBlockBlockQuotation(blocks=inner))
        else:
            blocks.extend(inner)
    return blocks
