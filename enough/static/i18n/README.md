# i18n — translated chrome + help content

One folder per non-English UI language (`fr`, `es`, `de`, `zh`, `ja`),
each holding `ui.json` (chrome strings), `help-docs.md` (the `(?)`
bubbles), and `help-center.md` (the manual). `en/` holds only the
canonical string catalog — English content itself lives inline in
`index.html`, in `static/help-docs.md`, and in `docs/HELP_CENTER.md`.

**Do not hand-edit a translation without reading `docs/I18N.md`** — it
documents the runtime mechanism, the structural contract these files
must keep (ids, tokens, heading skeletons, untranslated paths), and the
update process. `scripts/i18n_check.py` verifies the lot and
`tests/test_i18n.py` enforces it.
