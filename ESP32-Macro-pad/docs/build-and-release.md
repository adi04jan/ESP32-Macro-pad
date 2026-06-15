# Build & Release

How to build the Macropad Studio Windows installer and publish a GitHub release.

## Build the Windows installer

```sh
cd studio
npm install        # first time only (postinstall rebuilds the serialport native module)
npm run dist       # node build.js && electron-builder --win
```

Output lands in `studio/dist-build/`:

- `Macropad Studio-<version>-setup.exe` — the NSIS installer (~107 MB).
- `win-unpacked/` — the unpacked app (handy for quick testing).

The packaging is configured under the `build` key in
[`studio/package.json`](../studio/package.json):

- **Target:** NSIS, x64. Non-one-click installer that lets the user choose the
  install directory and creates desktop + Start-menu shortcuts.
- **App id:** `com.adi04jan.macropadstudio`.
- The `serialport` native module is unpacked from the asar (`asarUnpack`) so it
  loads at runtime.
- `macropad_default_templates.json` is bundled as an `extraResources` file.

> The app currently ships with the **default Electron icon** — no custom icon is
> set. Add an `.ico` and a `win.icon` / `nsis` entry in `package.json` to brand it.

## Cut a GitHub release

The installer is too large to commit, so it ships as a release asset.

1. Make sure the version is bumped where it matters and consistent:
   - `studio/package.json` → `version`
   - `config.h` → `FW_VERSION`
2. Commit and merge to `main`, then tag:
   ```sh
   git tag v<version>
   git push origin main --tags
   ```
3. Build the installer (`npm run dist`).
4. Create the release and attach the `.exe`:
   ```sh
   gh release create v<version> \
     "studio/dist-build/Macropad Studio-<version>-setup.exe" \
     --title "v<version>" --notes-file RELEASE_NOTES.md
   ```
   Or, without the GitHub CLI, create the release in the web UI
   (**Releases → Draft a new release**), pick the tag, and upload the `.exe`.

> **Auto-update:** `package.json` configures `build.publish` (GitHub), so
> `electron-builder` also emits **`latest.yml`** (and a `.blockmap`) in
> `dist-build/`. Upload **`latest.yml` + the `.exe` + the `.blockmap`** to the
> release — `electron-updater` reads `latest.yml` to detect and download updates.
> Without `latest.yml` attached, installed apps won't see the new version.

### Version

`2.0.0` was the v2 rewrite (modular non-blocking firmware + Macropad Studio).
`2.1.0` adds auto-update, finished Settings, LED-brightness / per-key-debounce,
and firmware safe-boot + watchdog.
