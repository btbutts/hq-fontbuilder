"""Compose one monospace terminal font from per-group donors, chosen in a web console.

kmscon-style consoles take missing glyphs from whatever fontconfig lists next; this tool
instead builds one font file per style in which every glyph group comes from the family the
user chose for it, scaled and aligned to a single cell. This pass provides the composer
web console (``compose``) that produces the configuration and the ``inspect`` coverage
report; the ``build`` mode that assembles the output fonts comes next.
"""

__version__ = "0.1.0"
