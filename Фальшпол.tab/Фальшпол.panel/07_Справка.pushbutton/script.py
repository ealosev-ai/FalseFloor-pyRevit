# -*- coding: utf-8 -*-

import io
import os
import re
import tempfile

from floor_i18n import tr  # type: ignore
from pyrevit import forms  # type: ignore


def _format_inline(text):
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)


def _markdown_to_html(markdown_text):
    html = []
    in_ul = False
    in_ol = False

    def close_lists():
        items = []
        nonlocal in_ul, in_ol
        if in_ul:
            items.append("</ul>")
            in_ul = False
        if in_ol:
            items.append("</ol>")
            in_ol = False
        return items

    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            html.extend(close_lists())
            continue

        if stripped.startswith("### "):
            html.extend(close_lists())
            html.append("<h3>{}</h3>".format(_format_inline(stripped[4:])))
            continue

        if stripped.startswith("## "):
            html.extend(close_lists())
            html.append("<h2>{}</h2>".format(_format_inline(stripped[3:])))
            continue

        if stripped.startswith("# "):
            html.extend(close_lists())
            html.append("<h1>{}</h1>".format(_format_inline(stripped[2:])))
            continue

        if stripped.startswith("- "):
            if in_ol:
                html.extend(close_lists())
            if not in_ul:
                html.append("<ul>")
                in_ul = True
            html.append("<li>{}</li>".format(_format_inline(stripped[2:])))
            continue

        ordered_match = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if ordered_match:
            if in_ul:
                html.extend(close_lists())
            if not in_ol:
                html.append("<ol>")
                in_ol = True
            html.append("<li>{}</li>".format(_format_inline(ordered_match.group(2))))
            continue

        html.extend(close_lists())
        html.append("<p>{}</p>".format(_format_inline(stripped)))

    html.extend(close_lists())
    return "".join(html)


def main():
    panel_dir = os.path.dirname(os.path.dirname(__file__))
    readme_path = os.path.join(panel_dir, "README.md")
    if not os.path.exists(readme_path):
        forms.alert(tr("help_file_not_found"), title=tr("help_title"))
        return

    with io.open(readme_path, "r", encoding="utf-8") as readme_file:
        content = readme_file.read()

    html = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <style>
        body {{ font-family: Segoe UI, sans-serif; margin: 24px auto; max-width: 980px; color: #202020; }}
        h1 {{ font-size: 24px; margin: 0 0 16px 0; }}
        h2 {{ font-size: 20px; margin: 24px 0 10px 0; }}
        h3 {{ font-size: 16px; margin: 18px 0 8px 0; }}
        p, li {{ font-size: 13px; line-height: 1.45; }}
        ul, ol {{ margin: 8px 0 12px 22px; }}
        code {{
            font-family: Consolas, monospace;
            background: #f1f3f5;
            border: 1px solid #dde2e6;
            border-radius: 3px;
            padding: 1px 4px;
        }}
    </style>
</head>
<body>{body}</body>
</html>
""".format(
        title=tr("help_html_title"),
        body=_markdown_to_html(content),
    )

    temp_dir = os.path.join(tempfile.gettempdir(), "falsepol_help")
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    html_path = os.path.join(temp_dir, "falsepol_help.html")
    with io.open(html_path, "w", encoding="utf-8") as html_file:
        html_file.write(html)

    os.startfile(html_path)


if __name__ == "__main__":
    main()
