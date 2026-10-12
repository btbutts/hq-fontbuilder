"""The research console: watch the fonts directory and serve the web UI.

The console is how the user researches donors and records choices; every choice is
written to ``composer.toml``. ``watcher`` polls the directory, ``state`` holds the
shared console state (library scan, choices, version counter), and ``web`` is the
HTTP server and its static pages.
"""
