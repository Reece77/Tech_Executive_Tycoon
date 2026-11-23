"""The Windows desktop build (M58): the game in its own window, installed like any program.

`tst.desktop.main` starts the API (serving the built front end, as M29's single-port server
does) on a free 127.0.0.1 port in this process, opens a pywebview window on it, and stops the
server when the window closes. The other modules hold what the window needs and are importable
without pywebview (tests, the API's desktop routes):

- `paths`: saves in Documents/Tech Startup Tycoon, settings and logs in app data;
- `instance`: one running copy (a second launch focuses the first window);
- `secrets`: the Anthropic API key in app data's `.env`, never logged;
- `imports`: first-run import of the repository's `saves` folder;
- `update`: the GitHub release check, checksum-verified download and pre-update backup;
- `context`: the running window's state, read by `tst.api.routers.desktop`.

Not part of the simulation: nothing here is imported by `tst.sim`.
"""
