#!/usr/bin/env python3
"""Check the generated site's local links, media, headings and structured data.

Run after tools/build.py. Uses only the Python standard library; does not fetch external URLs.
"""
import json
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.path = path
        self.ids, self.refs, self.styles, self.images = [], [], [], []
        self.h1 = 0
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if tag not in VOID:
            self.stack.append(tag)
        if attr.get('id'):
            self.ids.append(attr['id'])
        self.h1 += tag == 'h1'
        if tag == 'img':
            self.images.append(attr)
        if tag == 'link' and attr.get('rel') == 'stylesheet':
            self.styles.append(urlsplit(attr['href']).path)
        for name in ('href', 'src', 'poster'):
            if attr.get(name):
                self.refs.append(attr[name])
        for item in attr.get('srcset', '').split(','):
            if item.strip():
                self.refs.append(item.strip().split()[0])

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f'unbalanced closing tag: {tag}')
        else:
            self.stack.pop()

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)


def main():
    paths = [ROOT / 'index.html', ROOT / '404.html']
    for section in ('projects', 'publications', 'research', 'cv', 'contact', 'videos'):
        paths.extend((ROOT / section).rglob('index.html'))
    pages = {}
    errors = []
    for path in paths:
        page = Page(path)
        markup = path.read_text()
        page.feed(markup)
        pages[path] = page
        errors.extend(f'{path.relative_to(ROOT)}: {message}' for message in page.errors)
        if page.stack:
            errors.append(f'{path.relative_to(ROOT)}: unclosed tags {page.stack}')
        if page.h1 != 1:
            errors.append(f'{path.relative_to(ROOT)}: expected one h1, found {page.h1}')
        if page.styles.count('/assets/fieldbook.css') != 1:
            errors.append(f'{path.relative_to(ROOT)}: shared theme missing or duplicated')
        if any(n > 1 for n in Counter(page.ids).values()):
            errors.append(f'{path.relative_to(ROOT)}: duplicate IDs')
        for img in page.images:
            if not all(name in img for name in ('alt', 'width', 'height')):
                errors.append(f'{path.relative_to(ROOT)}: image missing alt or dimensions')
        for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', markup, re.S):
            try:
                json.loads(raw)
            except json.JSONDecodeError as exc:
                errors.append(f'{path.relative_to(ROOT)}: invalid JSON-LD: {exc}')
    checked = 0
    for path, page in pages.items():
        for ref in page.refs:
            url = urlsplit(ref)
            if url.scheme or url.netloc:
                continue
            dest = (ROOT / unquote(url.path).lstrip('/') if url.path.startswith('/')
                    else path.parent / unquote(url.path)) if url.path else path
            if dest.is_dir():
                dest /= 'index.html'
            dest = dest.resolve()
            checked += 1
            if not dest.is_file():
                errors.append(f'{path.relative_to(ROOT)}: missing {ref}')
            elif url.fragment and dest in pages and not url.fragment.startswith('t='):
                if unquote(url.fragment) not in pages[dest].ids:
                    errors.append(f'{path.relative_to(ROOT)}: missing anchor {ref}')
    if errors:
        raise SystemExit('\n'.join(errors))
    print(f'PASS: {len(pages)} pages, {checked} local references; balanced markup, unique IDs, '
          'one h1, image descriptions/dimensions, shared theme and JSON-LD.')


if __name__ == '__main__':
    main()
