# Roam
Roam is a **single-player** game that allows you to explore a procedurally-generated 2D world and interact with your surroundings. There are currently no plans to add multiplayer.

## Planning Document
The planning document can be found [here](./PLANNING.md)

## Controls
Key | Action
------------ | -------------
W / A / S / D (or Arrow Keys) | Move up / left / down / right
Shift (hold) or R (toggle) | Run
Ctrl (hold) or Z (toggle) | Crouch
G | Gather / Harvest mature crop
F | Place item / Interact
X | Look (examine the tile you are facing)
Left Mouse | Gather / Pick up / Harvest mature crop
Right Mouse | Place item / Plant seed on grass
1-0 | Select hotbar slot
`[` / `]` | Cycle hotbar left / right
Scroll Wheel | Cycle through hotbar
I | Open / Close inventory
M | Toggle minimap
= / - | Minimap zoom in / out
Page Up / Page Down (or `,` / `.`) | Show the map of the cave level above / below the one displayed
Home (or `/`) | Show the map of the level you are standing on again
C | Toggle camera follow mode
Middle Mouse (drag) | Reposition a HUD element — hotbar, status, energy bar or minimap (saved between sessions)
F1 (or H) | Toggle controls help overlay
F3 (or `\`) | Toggle debug info
F2 (or N) | Toggle NPC/CPC mode
L | Open Codex
Print Screen (or P) | Take screenshot
Esc | Quit (main menu) / Open menu (world) / Go back (other screens)
Left Mouse (outside inventory panel) | Drop entire cursor stack (inventory screen)
Middle Mouse (outside inventory panel) | Drop single item from cursor (inventory screen)
Right Mouse (inventory slot) | Select inventory slot (inventory screen)

> **Tip:** Keybindings are configurable in-game. Open the options menu and select **Controls** to view or remap bindings. Remapped keys are respected across all screens (world, inventory, stats, etc.).
>
> **Tip:** On keyboards without F-keys (e.g. Android / Userland), use **H** for the help overlay and **`\`** for debug info.
>
> **Tip:** In text / terminal mode (`--text`), a terminal can't detect held keys, so use the toggles **R** (run) and **Z** (crouch) instead of holding Shift / Ctrl. The active state is shown in the status bar. A terminal also can't send Print Screen — use **P** to save a `.txt` screenshot instead, and **`,`** / **`.`** / **`/`** in place of Page Up / Page Down / Home to page the minimap between cave levels.

## Download & Install (recommended)
The easiest way to play Roam — no Python and no command line. Grab the latest build from the [Releases page](https://github.com/Preponderous-Software/roam/releases):

- **Windows:** `Roam-<version>-Setup.exe` — a standard installer that adds Start Menu/Desktop shortcuts and an uninstaller. Prefer no install? Use `Roam-<version>-windows-portable.zip`.
- **macOS:** `Roam-<version>.dmg` — open it and drag `Roam.app` to Applications.

These builds aren't code-signed yet, so on first run Windows SmartScreen shows an "unknown publisher" prompt (choose **More info → Run anyway**) and macOS Gatekeeper may block the app (right-click it → **Open**). See issues #393 / #396.

## Run from Source (for developers)
Want the latest code, or to contribute? Run Roam from a clone. (To just play, use the [download above](#download--install-recommended).)
### Clone
1. If you don't have git installed, install it from [here](https://git-scm.com/downloads).
2. Clone the repository with the following command:
> git clone https://github.com/Preponderous-Software/roam.git

### Install Dependencies
3. If you don't have python installed, install it from [here](https://www.python.org/downloads/).
4. Install the dependencies with the following command:
> pip install -r requirements.txt

`requirements.txt` covers everything the game needs — pygame included — as lower bounds rather than exact pins, so pip can pick wheels that match your Python version.

### Run
5. Run the game with the following command:
> python src/roam.py

Roam auto-detects whether a display is available. If no display server is found (e.g. SSH without X forwarding, Android Userland without XServer), it switches to **text / TUI mode** automatically — no extra flags needed. You can also force text mode explicitly:
> python src/roam.py --text

### Command-line options
Run `python src/roam.py --help` to print this list.

Option | Effect
------ | ------
`--text` | Force text / TUI mode instead of the graphical frontend. Only needed to override a working display — text mode is selected automatically when none is available.
`--selftest` | Start up, load assets/schemas/config, then exit without opening a window. Used to verify a packaged build (see [Building a standalone executable](#building-a-standalone-executable-advanced)).
`-h`, `--help` | Print the usage summary and exit.

Any other argument is rejected with an error and a non-zero exit status.

## Run Script (Linux Only)
There is also a run.sh script you can execute if you're on linux which will automatically attempt to install the dependencies for you.

## Play in a Browser (from source)
Roam also runs in a browser. The Python game itself is executed client-side by [Pyodide](https://pyodide.org/) inside a Web Worker, so the server only ever hands out static files.

1. Build the bundle the browser downloads (`web/game.zip`):
> python3 web/build_zip.py
2. Start the static file server:
> python3 web/serve.py
3. Open <http://localhost:8080/play>.

Set `PORT` to serve somewhere else (`PORT=9000 python3 web/serve.py`). A plain `python -m http.server` will not do: the page allocates a `SharedArrayBuffer` to deliver input to the worker, which browsers only permit on a cross-origin-isolated page, and `web/serve.py` is what sends the required `Cross-Origin-Opener-Policy` / `Cross-Origin-Embedder-Policy` headers.

A `Dockerfile` is included that does both steps and exposes port 8080:
> docker build -t roam .
>
> docker run -p 8080:8080 roam

Saves made in the browser live in that browser's own storage (an IndexedDB database named `roam-saves`), not on the server — clearing site data clears them. Re-run `web/build_zip.py` after changing anything under `src/` or `schemas/`, otherwise the worker keeps unpacking the previously built bundle.

## Windows setup script (run from source)
If you're [running from source](#run-from-source-for-developers) on Windows, `install.ps1` is a setup *script* — the from-source counterpart to `run.sh`. It checks that Python and pip are available, installs the dependencies, and creates Desktop and Start Menu shortcuts so you can launch the game without using the command line. (For a normal install, use the `RoamSetup.exe` **installer** from [Download & Install](#download--install-recommended) instead — it needs no Python.)

1. [Clone or download](#clone) the repository.
2. Right-click `install.ps1` and choose **Run with PowerShell**.
   - If Windows blocks the script, open PowerShell in the project folder and run:
     > powershell -ExecutionPolicy Bypass -File .\install.ps1
3. Follow the prompts. When it finishes, launch Roam from the **Roam** Desktop/Start Menu shortcut, or by double-clicking `run.bat`.

If Python is not installed, the wizard opens the [Python download page](https://www.python.org/downloads/) for you — install it (make sure **Add python.exe to PATH** is checked) and run the wizard again.

To undo what the wizard created (the Desktop/Start Menu shortcuts and the generated `icon.ico`), run it with `-Uninstall`:
> powershell -ExecutionPolicy Bypass -File .\install.ps1 -Uninstall

By default your saves/settings/screenshots under `%APPDATA%\Roam` are kept; you'll be asked whether to delete them too, or pass `-RemoveData` to delete them without asking. It does not touch the cloned repository or your Python installation. (The `RoamSetup.exe` installer registers its own uninstaller in Add/Remove Programs instead — this `-Uninstall` flag is only for the script-based wizard above.)

### Building a standalone executable (advanced)
A self-contained Windows build that bundles Python and all dependencies can be produced with [PyInstaller](https://pyinstaller.org/):

> pip install -r requirements.txt pyinstaller
> pyinstaller roam.spec --noconfirm

This writes `dist\Roam\Roam.exe` along with its bundled `assets`, `schemas`, and `config.yml`. You can verify the bundle without launching the game using `dist\Roam\Roam.exe --selftest`.

To produce a setup wizard (a `RoamSetup.exe` that installs the game with Start Menu/Desktop shortcuts and an uninstaller), build the executable above, then compile the [Inno Setup](https://jrsoftware.org/isinfo.php) script with Inno Setup 6:

> "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" roam.iss

This writes `installer-output\RoamSetup.exe`. Run it (or `RoamSetup.exe /VERYSILENT` for an unattended install, which installs into `Program Files`) to install Roam; the wizard lets you choose between installing for all users (`Program Files`, requires admin) or for yourself only (no elevation required). User data is kept under `%APPDATA%\Roam` either way.

#### macOS
On macOS the same spec produces an app bundle (`dist/Roam.app`). Build it, then wrap it in a disk image:

> pip install -r requirements.txt pyinstaller
> pyinstaller roam.spec --noconfirm
> hdiutil create -volname Roam -srcfolder dist/Roam.app -ov -format UDZO dist/Roam.dmg

Open `Roam.dmg` and drag `Roam.app` to Applications. User data (saves, settings, screenshots) is kept under `~/Library/Application Support/Roam`.

### Where your data is stored
On Windows and macOS, Roam keeps your user data in a per-user directory so it stays with your account and works even when the game is installed somewhere read-only (`Program Files`, `/Applications`). On other platforms it stays next to the game.

Platform | Saves | Settings | Screenshots
------------ | ------------- | ------------- | -------------
Windows | `%APPDATA%\Roam\saves` | `%APPDATA%\Roam\config.yml` | `%APPDATA%\Roam\screenshots`
macOS | `~/Library/Application Support/Roam/saves` | `~/Library/Application Support/Roam/config.yml` | `~/Library/Application Support/Roam/screenshots`
Linux / other | `saves/` | `config.yml` | `screenshots/`

`%APPDATA%` is typically `C:\Users\<you>\AppData\Roaming`. The settings file is seeded from the shipped defaults the first time it is needed, so the version in the install directory is left untouched.

You can override the save location by setting `pathToSaveDirectory` in `config.yml`, or the whole saves directory by setting the `ROAM_SAVE_DIR` environment variable, which takes precedence over both `pathToSaveDirectory` and the table above. `ROAM_SAVE_DIR` applies to a server-side run of the game; saves made in the [browser build](#play-in-a-browser-from-source) are held by the browser, so it has no effect there.

### Usage reporting
Roam reports that it is being played, anonymously, so the number of installations actually in use can be seen. On launch it sends a `startup` event, and each time a save is opened a `world-loaded` event, to [trace](https://github.com/Stephenson-Software/trace) at `https://trace.danielstephenson.dev`. Each event carries the program name (`roam`) and the game version only — never a username, machine name, IP address, path or save name. The request is made on a background thread, never blocks or interrupts the game, and is dropped if the service cannot be reached.

Reporting is on by default. The first launch after installing a version with it logs a one-line notice and records the setting in your `config.yml` (see the table above for where that is). To turn it off, set:

```yaml
usageReportingEnabled: false
```

The [browser build](#play-in-a-browser-from-source) never reports. Setting the `ROAM_USAGE_REPORTING=0` environment variable also turns reporting off for a single run, which is what the test harness does. The client is the vendored `src/lib/trace_client.py` (standard library only).

## Support
You can find the support discord server [here](https://discord.gg/49J4RHQxhy).

## Authors and acknowledgement
### Developers
Name | Main Contributions
------------ | -------------
Daniel McCoy Stephenson | Creator

## Libraries
This project makes use of [graphik](https://github.com/Preponderous-Software/graphik) and [py_env_lib](https://github.com/Preponderous-Software/py_env_lib).

## 📄 License

This project is licensed under the **Preponderous Non-Commercial License (Preponderous-NC)**.  
It is free to use, modify, and self-host for **non-commercial** purposes, but **commercial use requires a separate license**.

> **Disclaimer:** *Preponderous Software is not a legal entity.*  
> All rights to works published under this license are reserved by the copyright holder, **Daniel McCoy Stephenson**.

Full license text:  
[https://github.com/Preponderous-Software/preponderous-nc-license/blob/main/LICENSE.md](https://github.com/Preponderous-Software/preponderous-nc-license/blob/main/LICENSE.md)
