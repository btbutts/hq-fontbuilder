# HQ-FontBuilder

### This project consists of two primary components, the _`font-composer`_ and the _`font-builder`_:
  - The **font-composer** allows this python tool tool monitor a directory for newly added fonts (seee explanation below for how to structure this), spins up a web interface, and hosts those TTF fonts on the interface so you can make selections as to which glyph categories you'd like to extract from each font for your new singular output custom font family, of which multiple styles may be generated like Bold, Regular, Light, Condensed, etc... This process will generate an output .toml config
  - The **font-builder** tool of this python module will generate output fonts from the `.toml` file you generated from within the **font-composer**.
  - This process is meant to help simplify, both interactively, yet programatically, the process of extracing desired glyph packs from multple fonts into one singluar, unique font pack.

## _Why this exists_

Compose one monospace terminal font from per-group donors. Consoles like kmscon take
missing glyphs from whatever fontconfig lists next — a fallback, not a design — so the
borrowed checkmarks, bullets and arrows have another size, weight and baseline than the
text around them. This tool instead builds **one font file per style in which every
glyph group comes from the family you chose for it**, fitted to a single cell.

The two components map to two commands:

* **`compose` — the font-composer** (implemented). Watches a directory of font
  families, spins up the web interface, shows a coverage table of glyph groups ×
  families, lets you inspect every glyph of a group drawn by each donor font inside
  the target cell, and records your choices in the output `.toml` config as you make
  them.
* **`build` — the font-builder.** Reads the `.toml` config and writes one TTF per
  requested style, plus a `NOTICE` file (see "Building the fonts" below).

A third command, **`inspect`**, prints one font's metadata and per-block coverage on
the command line — the quick way to reproduce the coverage measurements for any file.

## _The fonts directory convention_

```
fonts/                     <- next to font_composer/; empty in a release
  DejaVu/                  <- the folder name is the family label
    DejaVuSansMono.ttf
    DejaVuSansMono-Bold.ttf
  FiraCode/
    FiraCode-Regular.ttf
    ...
```

`fonts/` sits next to the `font_composer/` package (the directory is part of every
checkout and release, empty; its contents are never committed or shipped) and is the
directory the console watches unless the config (`[fonts] dir`) or `--fonts-dir` names
another. **This project ships no fonts**; the families named in this document are examples,
and you supply your own. `output/`, next to it, is where `build` writes the composed fonts
(also empty, also never committed).
One sub-folder per family; any TTF/OTF dropped into a folder belongs to that family.
Files are picked up automatically while the console runs (polled once a second, no
dependencies). Files that cannot be read are listed on the main page with the reason —
never silently skipped.

The families seeded for the terminal project (not committed; drop the files into the
folders yourself): DejaVu Sans Mono, Fira Code, JetBrains Mono (+NL), Source Code Pro,
and the Nerd Fonts builds of Fira Mono and Inconsolata, each in the plain and the
`Mono` (single-cell icons) variant.

## _Quick start_

Requires Python 3.12+ and [Bun](https://bun.sh) (Node.js is not needed). One script sets up everything on a fresh clone
(the Python virtualenv with `requirements.txt`, and the compiled web console):

```sh
./setup-build-env.sh
```

It is idempotent — re-running it only does what is missing. The two steps are also
available on their own: `./compile-spa.sh` recompiles just the web console (run it
after editing anything in `src/composer-web/`).

Inspect a font (metadata, fixed-width judgement, per-block coverage):

```sh
.fontbuilder.venv/bin/python -m font_composer inspect fonts/DejaVu/DejaVuSansMono.ttf
```

Run the font-composer web console:

```sh
.fontbuilder.venv/bin/python -m font_composer compose
```

That is the whole command; every option has a default (`--help` shows them, with
examples):

| Option | Default |
|---|---|
| `--fonts-dir DIR` | the config's `[fonts] dir`, else `fonts/` next to `font_composer/`; saved to the config |
| `--output-dir DIR` | the config's `[output] dir`, else `output/` next to `font_composer/`; saved to the config, **not** created (the build does that) |
| `--config FILE` | `font_composer.toml` next to `font_composer/` (untracked: it is in `.gitignore`) |
| `--host HOST` | `localhost`, which is both `127.0.0.1` and `::1` |
| `--port PORT` | chosen automatically, see below |
| `--monitor` | off: on a terminal, show the scrolling tail described below |

**On the terminal** the console keeps four lines on screen while it runs, the address to
open first:

```
The font_composer console is reachable at: http://localhost:8710/
	listening on IP Addresses: 127.0.0.1, ::1
	fonts: /path/to/fonts
	config: /path/to/font_composer.toml
```

Below them, like `tail -f`, are the last request lines (`::1 - - [..] "GET /fonts/... HTTP/1.1"
200 -`), never more than 60 % of the terminal's height, scrolling in place; the SPA's
version poll (every two seconds per open page) is left out so it does not push the rest
away. The bottom line reads `Press 'Q' to quit or 'R' to Reload`: **Q** (or Ctrl-C)
stops the console, **R** restarts it with the same command line, picking up code, fonts
and config afresh. With `--monitor`, or when the output is not a terminal (a pipe, a
log file), nothing is redrawn: the lines are printed one after the other, without end,
and a terminal still gets the Q and R keys.

The console has no authentication (it writes a file on this machine), which is why the default
is the loopback addresses only; give `--host` an interface address to listen elsewhere.

**Port.** Without `--port` the console reuses the port saved in the config (`[server]
port`) when it is free; otherwise it takes the first free port of `8700-9000`, then of
`18700-19000`, in steps of 5 (so the last digit is 0 or 5), and saves it. "In use" is
judged by connecting, so a dev server on the wildcard address (`*:8700`) is noticed too.
If that saved port has since been taken, a new one is chosen and the console says so. With
`--port N` the console uses exactly `N` (and saves it); if `N` is in use it stops with a
message: pick another with `--port`, or drop `--port` to have one chosen.

In the console:

* The **coverage table** has one row per glyph category and one column per family; a cell
  shows `present/total` and is green when complete, amber when partial, grey when
  empty. The numbers are those of the family's *reference style*, the upright cut
  nearest Regular (not a union over all its files: a composed style takes its glyphs
  from one file, so a union would claim glyphs no single file holds). `≠` marks a group
  on which the family's styles hold different glyphs. `Box Drawing` and
  `Block Elements` are *atomic*: they only count as sourced at 100%. The outlined cell
  is the family currently chosen for that group.
* The categories are the **Unicode blocks** of the Unicode Character Database's
  `Blocks.txt` (downloaded to `src/char-sets/` with the names list the first time it is
  needed, never committed), and the table lists only those in which at least one family
  has a glyph. The button left of the lock in the "Group" header opens **Select Glyph
  Categories**: hide the categories you do not need (this only hides the row; the build
  still honours the choices made in it), see in how many fonts each has glyphs (hover the
  count for the number per family), and switch the **simplified Glyph Category overlay**
  on or off. The overlay is on by default. It shows three categories of its own in place
  of the part of a block they cut out: ASCII letters and digits and other printable ASCII
  (Basic Latin), and Powerline (Private Use Area); the dialog marks them `overlay`. The
  overlay exists only in the console. What you choose in one of its categories is written
  as one pin per code point to `[generated_glyphs]`, under the official block name
  everything else uses; the order of an overlay category is kept by the browser, or in
  `[overlay_orders]` when you switch on **Store Overlay Categories in toml config**. The
  build never reads the overlay.
* **Click a cell** to open the group page (after a moment, once no second click follows;
  focusing a cell and pressing Enter opens it at once): every style of the family, every
  code point of the group, drawn by the font itself in a box the size of the base family's cell.
  The box is the cell a console would give the glyph (width = the base family's
  advance, height = its ascent + descent), the dashed red line is the baseline, and
  the glyph's origin is the cell's left edge, as in a terminal, so a donor whose advance
  or height differs visibly overflows. Each glyph is an SVG `<text>`, so the baseline is
  exactly where the base family's ascent puts it whatever the donor's own metrics are.
  A code point the font does not have is a hatched cell, never a glyph borrowed from
  another font. Groups of more than 512 code points (Nerd Font private use) draw only
  the glyphs a style holds, 256 at a time.
* **Double-click a cell** to add that family to the category's inheritance order, or to take
  it out when it is already in it (an atomic category refuses a family that does not cover
  it completely, and says so under the table). The **Coverage Table** button of the group
  page, and the browser's back button, return to the table at the place you left it, down
  the page and along the table.
* **Layout.** By default the cells are stacked in rows that never wrap and are
  left-aligned, so a column means the same thing in every row and every style: the ASCII
  letters and digits category
  is digits, then capitals, then lower case; any other category is cut in rows of 16 by code
  point, like the Unicode charts (the row label is `U+25A_`, the column is the last hex
  digit). The page scrolls sideways when a row is wider than the window. The
  **Enable glyph wrapping** switch at the top right of the page gives one wrapping run
  instead (the choice is remembered by the browser). The layout code is in
  `src/composer-web/src/lib/glyph/glyphLayout.ts` (pure functions, `bun run test`) and
  `glyph/GlyphGrid.svelte`.
* The **checkbox on the group page** (`use this family for this group`) adds the family
  to the group's **inheritance order**, at the end; unchecking removes it. Choose the
  families one after the other: the first is the group's first choice, and each following
  one fills in the code points the earlier ones have no glyph for. A code point that
  several families have is taken from the first of them. Every change is written to
  `font_composer.toml` immediately. Atomic categories (`Box Drawing`, `Block Elements`) take one
  family only, and a complete one.
* The **Composition so far** table at the bottom of the main page has one row per glyph
  category (`Glyph Categories`) and its families in order (`Font Inheritance Order`),
  with how many of the group's code points they cover together. A category with at
  least one family is a link to its **combined result**.
* The **combined result** page shows the group as one font: every code point drawn from
  the family that serves it (a colour bar under the cell says which; the list at the top
  gives the order, with controls to move a family earlier or later or to remove it).
  A **ring** in the corner of a cell marks a glyph that more than one family has: click
  it and a pop-out shows each family's version side by side; click one to pin that
  glyph to that family (a filled dot), or choose "use the inheritance order again". Pins
  are written to `[glyphs]`. Atomic groups cannot be mixed, so they have no pop-out.
* The **Style mapping** dialog (the button at the top right of the main page) shows, for
  every family in use (rows) and every output style (columns), which of the family's
  style files serves it, and lets you pick another. See "How style files are matched"
  below.
* **Hover a glyph** for its official Unicode name (from the Unicode Character Database's
  `NamesList.txt`, which the console downloads to `src/char-sets/` the first time it
  needs it and which is never committed), its code point, and what the fit does to it.
* The **Dark mode** switch (top right) follows your system until you use it, then
  remembers your choice.

## _The configuration file_

`font_composer.toml` is created with sensible defaults on first run. The console writes
`[groups]`, `[glyphs]`, `[styles.*]` and `[server] port`; everything else is yours to
hand-edit, comments included, and survives the console's saves. You may edit the file
while the console runs: it notices the change (and a file that does not parse is
reported on the main page and never overwritten):

```toml
[output]
family = "Console Mono"
dir = "output"                     # where `build` writes the fonts (compose --output-dir)
styles = ["Regular", "Bold"]       # the styles built: Regular and Bold until you pick more
consolidate_styles = true          # how the style list is shown (similar styles as one entry)
style-names = { Oblique = "Italic" }   # optional: a style built under another name (see below)

[fonts]
dir = "fonts"                      # where the source fonts are (compose --fonts-dir)

[cell]
base = "FiraCode"                  # family that defines the cell: advance, ascent, descent
fit = "base"

[groups]                           # written by the console: Unicode block -> inheritance order
"Latin-1 Supplement" = ["FiraCode"]
"General Punctuation" = ["FiraCode", "JetBrainsMono", "DejaVu"]   # first choice first
Arrows = ["DejaVu", "FiraCode"]

[glyphs]                           # written by the console: code points pinned to a family
"U+2714" = { family = "DejaVu" }   # (a bare string works too: "U+2714" = "DejaVu")

# Written by the console from the category overlay; the first family serves the glyph and
# the others are the fallbacks of a style file that lacks it. Do not edit this table.
[generated_glyphs]
"U+0041" = ["FiraCode", "JetBrainsMono"]

# Optional (Select Glyph Categories > Store Overlay Categories in toml config): the orders
# of the overlay categories, for other browsers. The build ignores it.
[overlay_orders]
"overlay:ascii-alnum" = ["FiraCode", "JetBrainsMono"]

[styles.Bold]                      # written by the console: which file serves an output style
DejaVu = "DejaVuSansMono-Bold.ttf" # (a style name such as "Bold" is accepted too)

[server]                           # written by the console
port = 8710

# hand-editable extras the build will honour: [group-options.<id>] (how donor glyphs
# are fitted to the cell).
```

`[groups]` still accepts a plain string for a block (`Arrows = "DejaVu"` is a list of
one). Group ids of earlier versions (`arrows`, `alnum`, `latin-ext-b` ...) are not block
names and are ignored: rebuild the choices with the block names. TOML was kept for the file: it has ordered arrays, comments and inline tables, and
the console and a human edit the same file.

### Glyphs that do not fit the cell

A donor's glyph is judged by its **ink** (the outline's bounding box) against the cell of
the base family, `[0, advance] x [descent, ascent]`. The group and combined-result pages
show the glyphs **fitted** by default. Turn on **Preview unfitted glyphs** to see the
donor's originals: the cells the base cell cuts off are outlined red, and each style says
how many. The rules are in `font_composer/common/fit.py` (pure functions, tested).

Every Unicode block is fitted **together, as a category**, and never stretched:

* **One scale per category** (`text`: Basic Latin, Latin-1 Supplement, Latin Extended-A, -B
  and Additional, Greek and Coptic, Cyrillic; `connectors`: Box Drawing, Block Elements;
  `symbols`: every other block, each by itself: arrows, mathematics, punctuation,
  dingbats, icons, ...). Shrinking only the glyph that offends would make it smaller
  than its look-alikes (`ĺ` against `ľ`, one box corner against the next), so one
  family's glyphs of a category get **one scale in both directions**, just enough for its
  offenders, applied to all of them about a fixed anchor (the baseline and the horizontal
  middle of the cell for text and symbols; the centre of the donor's frame for box
  drawing, so they keep lining up), plus the least extra shift or proportional shrink a
  glyph still needs. The scale has a floor (5% for text, 10% for symbols, 25% for box
  drawing: `CLASS_FLOORS`), so that a handful of outliers, such as an accented Greek
  capital taller than any letter, cannot make a whole alphabet visibly smaller; the
  outliers are fitted on their own, still in proportion. A font that *is* the base cell
  keeps its box drawing.
* **Pieces that must join their neighbours** are the one exception, fitted glyph by glyph
  (`is_joined`: the powerline symbols U+E0A0-U+E0D4, and the pieces of large brackets,
  braces, integrals and sums, U+2320-2321 and U+239B-23B3):

| Class | What it is | Correction |
|---|---|---|
| `category` | any glyph of a category fitted together | the category's one scale, plus what it still needs |
| `bleed` | past the cell by at most 0.02 em; fonts do it on purpose so neighbours show no seam | kept |
| `frame` | a piece designed to span the cell so neighbours join | the donor's frame (or cell) is fitted onto the base cell, one map per font family |
| `oversize` | a joined piece wider or taller than the cell | scaled uniformly to fit |
| `offset` | fits in size, sits partly outside (another line box) | moved the least that brings it inside |

Connectors that run past the cell on purpose (Fira Code's box lines) are fitted by their
frame and cut at the cell edge, not shrunk. The preview is a visualisation: it draws each glyph through the plan, but where box
drawing must also *join* its neighbours the build needs more than this (see the plan
document, "Glyph fitting").

### Building the fonts

```sh
.fontbuilder.venv/bin/python -m font_composer build   # font_composer.toml: fonts/ -> output/
.fontbuilder.venv/bin/python -m font_composer build --output-dir DIR --on-missing nearest
```

The source and output directories come from the config the console wrote (`[fonts] dir`,
`[output] dir`); `--fonts-dir` and `--output-dir` override them, and the output directory
is created when it does not exist. One unhinted TrueType file per style you included (**Style Mapping > the edit button in the table's header** lists
them, merged by weight and slant when **Consolidate Similar Font Styles** is on, and
includes or excludes them; Regular and Bold are included to begin with), named `<Family>-<Style>.ttf`
(`Console Mono` becomes `ConsoleMono-Regular.ttf`), and a `NOTICE` file next to them that
lists every font the result is made of with its copyright and licence text.

* **Where glyphs come from.** Each block's inheritance order, the generated pins and the `[glyphs]` pins decide
  the donor of a code point (the same resolution the console shows); it is drawn from the
  donor's file for *that output style*, fitted to the base cell by the plan the console
  previews, and given the base cell's advance. Every code point no group serves keeps the
  **base family's own glyph** (so the font is complete, not just the chosen groups). A
  group with more families than one falls back to the next family when a style file lacks
  a glyph; an atomic group never mixes, and half a Box Drawing set refuses the build.
* **Box drawing joins.** All box and block glyphs of a donor get one map that puts the
  donor's frame exactly on the base cell; what overshoots on purpose is cut at the cell
  edge. The build then checks that each connector still reaches the edges it was drawn to.
* **A style a family does not have.** Matching is exact in weight and slant (the rules
  below). When a family has no Bold, the build asks (on a terminal): use a file of the
  family as it is (the nearest weight is offered), **synthesize** a bold from the nearest
  lighter file (the outline is redrawn at small offsets), or stop. The answer is written
  to `[styles.<Output>]`, as a file name, `synthesize`, or `synthesize:<file>`, so it is
  asked once. `--on-missing nearest|synthesize|fail` decides without asking; without a
  terminal the build never guesses and stops.
* **Variable fonts** are instanced at the output style's weight. TrueType outlines are
  made from CFF donors with cubic-to-quadratic conversion.
* **Verification** reopens each written file and fails the build (and deletes the file)
  on: a code point map that differs from the plan, a glyph whose advance is not the cell,
  a letter of a donor cut off by the cell, a connector that no longer joins. Letters of
  the base font itself that leave its cell are reported, not changed.
* **Not yet:** `[group-options.*]` (per-group scale and alignment), kerning and ligatures
  (dropped on purpose: terminals do no shaping), hinting, and glyph-level checks by
  rendering with FreeType.

### How style files are matched

Style *names* differ between families for what is the same style (`Oblique` and
`Italic`, `Book` and `Regular`, `Demi` and `SemiBold`), so a family's file is never found by
name. Every font carries two numbers that mean the same everywhere, the OS/2 weight class
(100 Thin, 300 Light, 400 Regular, 500 Medium, 600 SemiBold, 700 Bold, 800 ExtraBold,
900 Black) and its slant (the italic bit, the mac style bit or a non-zero italic angle). An
output style name is turned into such a pair (`Bold Italic` is 700 italic; the spellings
`Oblique`, `Slanted`, `Demi`, `Heavy`, `Book`, `Roman` ... are known), and a file is picked
by these rules, in order:

1. a file (or style name) given for that family in `[styles.<Output>]` wins;
2. only files with the **same slant** are considered: an italic style is never served by
   an upright file, and nothing is slanted artificially; a family without an italic has
   no donor for an italic output style until you map one;
3. among them the weight **equal** to the output style's, else the nearest **similar**
   weight, else the **nearest** of all; two files equally near: the lighter one.

Similar weights are one family of styles: **Thin, ExtraLight and Light**, and **Medium,
SemiBold and Black** (listed as **SemiBold**; upright or italic alike, and `Oblique` is
`Italic`). Regular, Bold and
ExtraBold stand alone. The *Consolidate Similar Font Styles* switch uses the same families
for both the list and the style mapping: with it on, an included entry is one output
style (including Black builds SemiBold), so the mapping has one column for it and picks
the best file of each family by the rules above. A family with no
Bold gets a prompt (see "Building the fonts"); one with a SemiBold for a Medium does not. The
Style mapping dialog shows the result and the reason for every pair.

Including or excluding an entry applies to every style merged into it, and switching the
switch off keeps each of them as it was: with *Light Italic* included, *ExtraLight Italic*
and *Thin Italic* are included too, each on its own once the entries are spelled out
(`[output] styles` then names all of them), and a style left out stays out.

**Renaming a style.** The pencil in a column header of the Style mapping dialog gives that
output style another name (`Oblique` built as `Italic`). The name the fonts give stays the
key everything is tracked by (`[styles.<Output>]`, `styles`); the new name, saved as
`[output] style-names`, is what the font file, its name table and the console show, and it
wins over the original in the build. It must be unique: not the name of another style
(either listing) and not another style's custom name. Weight and slant still come from the
original style, so a style renamed `Slanted` is still flagged italic. (Variable fonts are
read as their default instance for now; the build will instantiate them.)

## Development

```sh
.fontbuilder.venv/bin/pytest                          # tests (tiny fonts built with FontBuilder)
.fontbuilder.venv/bin/ruff check font_composer tests
.fontbuilder.venv/bin/pylint font_composer tests
.fontbuilder.venv/bin/pyright
```

### _Web console source_

The console served by `compose` is a SvelteKit + TypeScript + TailwindCSS single-page
app whose source lives in `src/composer-web/` (requires [Bun](https://bun.sh); Node.js is not needed). Compile it with:

```sh
./compile-spa.sh     # bun install + build, into font_composer/composer/web/static/
```

or, from inside `src/composer-web/`, `bun --bun run build` directly (`bun --bun run check`
runs svelte-check, TypeScript strict; `bun --bun run test` runs the unit tests). `--bun`
makes vite, svelte-kit and svelte-check run on Bun's runtime instead of Node.js;
`src/composer-web/bunfig.toml` turns it on for every `bun run`, so leaving it off is safe.
The lockfile is `bun.lock`; `bun install` updates it, `bun install --frozen-lockfile` (what
CI uses) fails instead.

**Layout of `src/composer-web/src/`.** `routes/` holds the three pages (the coverage table,
a family's glyphs of one group, the combined result). `lib/` holds the reusable parts,
one folder per kind:

| Path | What is in it |
|---|---|
| `lib/styles.svelte.ts` | every colour of the site (`colors.<purpose>`, light and dark side by side) and the `theme` rune; the only place a colour is written |
| `lib/glyph/` | drawing glyphs: `GlyphCell`, `GlyphGrid`, `GlyphChooser` (the per-glyph pop-up), `glyphLayout` (pure, tested), `fitDisplay`, `families` (family colours, @font-face) |
| `lib/toggle/` | switches: `Toggle`, `ThemeToggle`, `ViewToggles`, and `viewOptions` (the state they set) |
| `lib/modal/` | dialogs: `StyleMappingModal` |
| `lib/layout/` | page structure: `PageHeader` (the full-width band) and `StickyBar` (the toolbar that sticks) |
| `lib/tooltip/` | the single tooltip host and the `tip()` helper elements use to describe themselves |
| `lib/data/` | talking to the Python console: `api` (types and requests), `console` (the polling store), `unicodeNames` |

`app.css` only imports Tailwind and declares the class-based `dark:` variant.

**Python owns the webserver.** `python -m font_composer compose` is the only process
you run: it watches the fonts directory, serves the JSON API and font files, and hosts
the compiled SPA — no Bun/vite process is needed at runtime. The SPA must simply have
been compiled once on this checkout (and again after any web source edit); until it
has, page requests get a 503 explaining how to compile.

The compiled output in `font_composer/composer/web/static/` is a build artifact and
is **not committed** — it only exists in build contexts (a development checkout, or
the release workflow bot, which compiles the SPA and tarballs it into the release).
The build wipes and rewrites that directory, so you choose when to recompile.

For frontend development only, `bun --bun run dev` gives Vite's live-reload dev server; it
proxies `/api` and `/fonts` to the Python console on `localhost`, which must run
alongside it. The port is read from `font_composer.toml` (`[server] port`, saved by the
console) or from the `COMPOSER_PORT` environment variable. This is optional — plain `./compile-spa.sh` plus the Python console is
the normal loop.

The Python server serves any unknown non-API path as the SPA fallback `200.html`, so
client-side routes like `/group?family=…&group=…` work on a hard refresh.

## _Releases_

The tarball holds the sources, the compiled web console and an empty `fonts/`
directory; no fonts are shipped.

Pushing a version tag runs `.github/workflows/release.yml` (it can also be started by
hand from the Actions tab):

```sh
git tag -a v0.1.0 -m "hq-fontbuilder 0.1.0" && git push origin v0.1.0
```

The workflow sets up Python and Node, runs `./setup-build-env.sh` (which compiles the
SPA on the fresh checkout), runs the tests, linters and svelte-check, then builds
`hq-fontbuilder-<version>.tar.gz`: the tracked sources listed in
`.github/release-files.txt` plus the compiled web console. The tarball is smoke-tested
(SPA present, test suite green inside it), checksummed, and published as a GitHub
release. Tags below 1.0.0 or with a suffix such as `-rc1` become pre-releases.
