# font-composer

Compose one monospace terminal font from per-group donors. Consoles like kmscon take
missing glyphs from whatever fontconfig lists next — a fallback, not a design — so the
borrowed checkmarks, bullets and arrows have another size, weight and baseline than the
text around them. This tool instead builds **one font file per style in which every
glyph group comes from the family you chose for it**, fitted to a single cell.

The tool has two modes:

* **`serve` — the research console** (implemented). Watches a directory of font
  families, shows a coverage table of glyph groups × families in a web page, lets you
  inspect every glyph of a group drawn by each donor font inside the target cell, and
  records your choices in `composer.toml` as you make them.
* **`build` — the font assembler** (not implemented yet; the command exists and says
  so). Will read `composer.toml` and write one TTF per requested style.

A third command, **`inspect`**, prints one font's metadata and per-group coverage on
the command line — the quick way to reproduce the coverage measurements for any file.

## The fonts directory convention

```
fonts/
  DejaVu/                  <- the folder name is the family label
    DejaVuSansMono.ttf
    DejaVuSansMono-Bold.ttf
  FiraCode/
    FiraCode-Regular.ttf
    ...
```

One sub-folder per family; any TTF/OTF dropped into a folder belongs to that family.
Files are picked up automatically while the console runs (polled once a second, no
dependencies). Files that cannot be read are listed on the main page with the reason —
never silently skipped.

The families seeded for the terminal project (not committed; drop the files into the
folders yourself): DejaVu Sans Mono, Fira Code, JetBrains Mono (+NL), Source Code Pro,
and the Nerd Fonts builds of Fira Mono and Inconsolata, each in the plain and the
`Mono` (single-cell icons) variant.

## Quick start

Requires Python 3.12+. Set up the environment once:

```sh
python3 -m venv .fontbuilder.venv
.fontbuilder.venv/bin/pip install fonttools pytest ruff pylint pyright
```

Inspect a font (metadata, fixed-width judgement, per-group coverage):

```sh
.fontbuilder.venv/bin/python -m font_composer inspect fonts/DejaVu/DejaVuSansMono.ttf
```

Run the research console and open <http://localhost:8765>:

```sh
.fontbuilder.venv/bin/python -m font_composer serve --fonts-dir fonts --config composer.toml
```

In the console:

* The **coverage table** has one row per glyph group and one column per family; a cell
  shows `present/total` and is green when complete, amber when partial, grey when
  empty. `box-drawing` and `block-elements` are *atomic*: they only count as sourced
  at 100%. The outlined cell is the family currently chosen for that group.
* **Click a cell** to open the group page: every style of the family, every code point
  of the group, drawn by the font itself inside a box the size of the base family's
  cell (cell edges and baseline shown, so overflow and misalignment are visible).
* The **radio on the group page** chooses that family as the source of the group;
  choosing another family elsewhere replaces the choice. Every choice is written to
  `composer.toml` immediately.
* The **summary** at the bottom of the main page shows the composition so far and the
  groups still without a source, with the families that could fully cover them.

## The configuration file

`composer.toml` is created with sensible defaults on first run. The console only ever
writes the `[groups]` table (group id → family label); everything else is yours to
hand-edit and survives the console's saves:

```toml
[output]
family = "Console Mono"
styles = ["Regular", "Bold"]

[cell]
base = "FiraCode"          # family that defines the cell: advance, ascent, descent
fit = "base"

[groups]                   # written by the console
box-drawing = "FiraCode"
arrows = "DejaVu"

# hand-editable extras the build will honour: [group-options.<id>], [glyphs]
# (single-glyph overrides), [styles.<Style>] (donor style per target style).
```

## Development

```sh
.fontbuilder.venv/bin/pytest                          # tests (tiny fonts built with FontBuilder)
.fontbuilder.venv/bin/ruff check font_composer tests
.fontbuilder.venv/bin/pylint font_composer tests
.fontbuilder.venv/bin/pyright
```
