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
* **`build` — the font-builder** (not implemented yet; the command exists and says
  so). Will read the `.toml` config and write one TTF per requested style.

A third command, **`inspect`**, prints one font's metadata and per-group coverage on
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
directory the console watches unless you pass `--fonts-dir`.
One sub-folder per family; any TTF/OTF dropped into a folder belongs to that family.
Files are picked up automatically while the console runs (polled once a second, no
dependencies). Files that cannot be read are listed on the main page with the reason —
never silently skipped.

The families seeded for the terminal project (not committed; drop the files into the
folders yourself): DejaVu Sans Mono, Fira Code, JetBrains Mono (+NL), Source Code Pro,
and the Nerd Fonts builds of Fira Mono and Inconsolata, each in the plain and the
`Mono` (single-cell icons) variant.

## _Quick start_

Requires Python 3.12+ and node/npm. One script sets up everything on a fresh clone
(the Python virtualenv with `requirements.txt`, and the compiled web console):

```sh
./setup-build-env.sh
```

It is idempotent — re-running it only does what is missing. The two steps are also
available on their own: `./compile-spa.sh` recompiles just the web console (run it
after editing anything in `src/composer-web/`).

Inspect a font (metadata, fixed-width judgement, per-group coverage):

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
| `--fonts-dir DIR` | `fonts/` next to `font_composer/` |
| `--config FILE` | `composer.toml` next to `font_composer/` (untracked: it is in `.gitignore`) |
| `--host HOST` | `localhost`, which is both `127.0.0.1` and `::1` |
| `--port PORT` | chosen automatically, see below |
| `--monitor` | off: on a terminal, show the scrolling tail described below |

**On the terminal** the console keeps four lines on screen while it runs, the address to
open first:

```
The font_composer console is reachable at: http://localhost:8710/
	listening on IP Addresses: 127.0.0.1, ::1
	fonts: /path/to/fonts
	config: /path/to/composer.toml
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

* The **coverage table** has one row per glyph group and one column per family; a cell
  shows `present/total` and is green when complete, amber when partial, grey when
  empty. The numbers are those of the family's *reference style*, the upright cut
  nearest Regular (not a union over all its files: a composed style takes its glyphs
  from one file, so a union would claim glyphs no single file holds). `≠` marks a group
  on which the family's styles hold different glyphs. `box-drawing` and
  `block-elements` are *atomic*: they only count as sourced at 100%. The outlined cell
  is the family currently chosen for that group.
* **Click a cell** to open the group page: every style of the family, every code point
  of the group, drawn by the font itself in a box the size of the base family's cell.
  The box is the cell a console would give the glyph (width = the base family's
  advance, height = its ascent + descent), the dashed red line is the baseline, and
  the glyph's origin is the cell's left edge, as in a terminal, so a donor whose advance
  or height differs visibly overflows. Each glyph is an SVG `<text>`, so the baseline is
  exactly where the base family's ascent puts it whatever the donor's own metrics are.
  A code point the font does not have is a hatched cell, never a glyph borrowed from
  another font. Groups of more than 512 code points (Nerd Font private use) draw only
  the glyphs a style holds, 256 at a time.
* **Layout.** By default the cells are stacked in rows that never wrap and are
  left-aligned, so a column means the same thing in every row and every style: `alnum`
  is digits, then capitals, then lower case; any other group is cut in rows of 16 by code
  point, like the Unicode charts (the row label is `U+25A_`, the column is the last hex
  digit). The page scrolls sideways when a row is wider than the window. The
  **Enable glyph wrapping** switch at the top right of the page gives one wrapping run
  instead (the choice is remembered by the browser). The layout code is in
  `src/composer-web/src/lib/glyphLayout.ts` (pure functions, `npm test`) and
  `GlyphGrid.svelte`.
* The **checkbox on the group page** (`use this family for this group`) adds the family
  to the group's **inheritance order**, at the end; unchecking removes it. Choose the
  families one after the other: the first is the group's first choice, and each following
  one fills in the code points the earlier ones have no glyph for. A code point that
  several families have is taken from the first of them. Every change is written to
  `composer.toml` immediately. Atomic groups (`box-drawing`, `block-elements`) take one
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
* The **Style mapping** page (a link at the top of the main page) shows, for every
  output style and every family in use, which of the family's style files serves it, and
  lets you pick another. See "How style files are matched" below.

## _The configuration file_

`composer.toml` is created with sensible defaults on first run. The console writes
`[groups]`, `[glyphs]`, `[styles.*]` and `[server] port`; everything else is yours to
hand-edit, comments included, and survives the console's saves. You may edit the file
while the console runs: it notices the change (and a file that does not parse is
reported on the main page and never overwritten):

```toml
[output]
family = "Console Mono"
styles = ["Regular", "Bold"]       # the output styles; names such as "Bold Italic" work too

[cell]
base = "FiraCode"                  # family that defines the cell: advance, ascent, descent
fit = "base"

[groups]                           # written by the console: group -> inheritance order
alnum = ["FiraCode"]
punctuation = ["FiraCode", "JetBrainsMono", "DejaVu"]   # first choice first
arrows = ["DejaVu", "FiraCode"]

[glyphs]                           # written by the console: code points pinned to a family
"U+2714" = { family = "DejaVu" }   # (a bare string works too: "U+2714" = "DejaVu")

[styles.Bold]                      # written by the console: which file serves an output style
DejaVu = "DejaVuSansMono-Bold.ttf" # (a style name such as "Bold" is accepted too)

[server]                           # written by the console
port = 8710

# hand-editable extras the build will honour: [group-options.<id>] (how donor glyphs
# are fitted to the cell).
```

`[groups]` still accepts a plain string for a group (`alnum = "FiraCode"` is a list of
one). TOML was kept for the file: it has ordered arrays, comments and inline tables, and
the console and a human edit the same file.

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
3. among them the weight **equal** to the output style's, else the **nearest**; two files
   equally near: the lighter one.

Medium (500) and Black (900) are different weights and are never folded together. The
Style mapping page shows the result and the reason for every pair. (Variable fonts are
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
app whose source lives in `src/composer-web/` (requires Node/npm). Compile it with:

```sh
./compile-spa.sh     # npm install + build, into font_composer/composer/web/static/
```

or, from inside `src/composer-web/`, `npm run build` directly (`npm run check` runs
svelte-check, TypeScript strict; `npm test` runs the glyph layout unit tests).

**Python owns the webserver.** `python -m font_composer compose` is the only process
you run: it watches the fonts directory, serves the JSON API and font files, and hosts
the compiled SPA — no npm/vite process is needed at runtime. The SPA must simply have
been compiled once on this checkout (and again after any web source edit); until it
has, page requests get a 503 explaining how to compile.

The compiled output in `font_composer/composer/web/static/` is a build artifact and
is **not committed** — it only exists in build contexts (a development checkout, or
the release workflow bot, which compiles the SPA and tarballs it into the release).
The build wipes and rewrites that directory, so you choose when to recompile.

For frontend development only, `npm run dev` gives Vite's live-reload dev server; it
proxies `/api` and `/fonts` to the Python console on `localhost`, which must run
alongside it. The port is read from `composer.toml` (`[server] port`, saved by the
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
