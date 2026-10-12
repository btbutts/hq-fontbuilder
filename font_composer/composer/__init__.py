"""The font-composer: watch the fonts directory and serve the web console UI.

The composer is how the user researches donors and records choices; every choice is
written to the output ``.toml`` config. ``watcher`` polls the directory, ``state``
holds the shared console state (library scan, choices, version counter), and ``web``
is the HTTP server and its static pages.
"""
