# shortcuts/

Optional macOS launchers that let you start `enough` without typing it
in a terminal each time. Both are templates — they don't do anything
useful from inside `~/enough/`. Use them as described below.

For the first-time installer launcher, see `install-enough.command` at
the repo root.

## `enough-on.command` — per-project double-click launcher

```bash
cp ~/enough/shortcuts/enough-on.command ~/some-project/
```

Then, in Finder, double-click `~/some-project/enough-on.command`. macOS
opens a Terminal window, `cd`s into the project folder, and runs
`enough` there. You see the launch banner and any output; ⌘W or ⌃C
stops it.

First time only on a fresh machine, macOS Gatekeeper may say "can't be
opened, unidentified developer." Right-click → Open once and macOS
trusts it forever after.

Double-clicking the template directly (`~/enough/shortcuts/enough-on.command`)
prints a hint reminding you to copy it out first — the CLI itself
refuses to launch inside `~/enough/`.

## `setup-quick-action.sh` — Finder right-click integration

Run once:

```bash
bash ~/enough/shortcuts/setup-quick-action.sh
```

Installs a "Launch in enough" Quick Action (Service) into
`~/Library/Services/`. After that, **right-click any folder in Finder
→ Quick Actions → Launch in enough** opens a Terminal pointed at that
folder with `enough` running.

If the menu item doesn't appear, you may need to enable it once:
**System Settings → Keyboard → Keyboard Shortcuts → Services → Files
and Folders → check "Launch in enough"**.

To uninstall:

```bash
rm -rf "$HOME/Library/Services/Launch in enough.workflow"
/System/Library/CoreServices/pbs -flush
```
