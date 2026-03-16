"""Helpers for rendering HTML email templates."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_ENV = Environment(
    loader=FileSystemLoader(PROJECT_ROOT),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_html_template(template_path: str, **context: object) -> str:
    """Render an HTML template from a project-relative path."""

    template = TEMPLATE_ENV.get_template(template_path)
    return template.render(**context)
