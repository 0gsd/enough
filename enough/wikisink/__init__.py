"""wikisink — enough's offline Wikipedia subsystem.

A Kiwix ZIM archive of Wikipedia on disk, browsed in-app (🚰), layered
with user data: an overlay of live-refreshed articles, preserved copies
of deleted articles, comments, pageview-ranking snapshots, and update
("wikisink") run state.

Submodules import `libzim` lazily so enough still boots — and every
other feature keeps working — when the wheel isn't installed.
"""
