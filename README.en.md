# XD SVN Tools

**English** · [简体中文](README.md)

[![Windows build](https://github.com/Binaryinject/XD-SVN-Tools/actions/workflows/build-windows.yml/badge.svg)](https://github.com/Binaryinject/XD-SVN-Tools/actions/workflows/build-windows.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A Windows diff and three-way merge tool for local Adobe XD `.xd` files, with TortoiseSVN integration.

Inspect changes by node ID, compare colored lines, merge independent edits automatically, and resolve conflicts individually. The interface follows the Windows app theme by default, with optional light and dark overrides.

> This is an independent experimental utility, not an official Adobe SDK. Open merged files in XD and verify layout, components, and interactions before marking SVN conflicts as resolved. Start with copies of your project files.

## Download and install

1. Open [GitHub Actions](https://github.com/Binaryinject/XD-SVN-Tools/actions/workflows/build-windows.yml) and select a successful run.
2. Download `XD-SVN-Tools-<version>-windows-x64` from **Artifacts** and extract the downloaded archive. GitHub sign-in is required to download workflow artifacts.
3. Run `XD-SVN-Tools-Setup-<version>.exe` and click the install and integrate button.

The installer uses `%LOCALAPPDATA%\Programs\XD-SVN-Tools` and registers `.xd` diff and merge commands for the current user. Administrator rights, Python, Node.js, and Git are not required by the installed app. Install TortoiseSVN first to invoke the tool from SVN.

In-place upgrades are supported. Uninstall through Windows Installed Apps to restore the previous `.xd` configuration. If you switched to another tool after installation, the uninstaller preserves that newer configuration.

Each build provides:

| File | Purpose |
| --- | --- |
| `XD-SVN-Tools-Setup-<version>.exe` | Install or upgrade and register TortoiseSVN commands |
| `XD-SVN-Tools-<version>-win-x64.zip` | Portable app; extract everything and run `XD-SVN-Tools.exe` |
| `SHA256SUMS-<version>.txt` | SHA-256 hashes for the installer and portable ZIP |

Builds target Windows x64 and have been validated on Windows 11. The installer requires .NET Framework 4.8. Generated installers are currently unsigned. The application interface is in Chinese; this English README documents its operation.

## Features

- **Structural diff:** browse changed JSON properties grouped by archive entry and node ID.
- **Line diff:** aligned panes, original line numbers, synchronized scrolling, and previous/next change navigation. Red means deletion, green addition, and yellow modification; changed characters receive stronger emphasis.
- **Three-way merge:** combine independent MINE and THEIRS changes relative to their common BASE.
- **Visible merge status:** green for automatically merged items, red for unresolved conflicts, and blue for manually resolved items, with counts for each category.
- **Checked saves:** saving is blocked while conflicts or basic reference errors remain. Existing output is backed up to `.bak`; the ZIP is verified before replacement.
- **Appearance:** follow the Windows app theme and update within about one second of a system change, or remember a manual light/dark override.

## Usage

### Compare two revisions

Choose the original file as BASE and the modified file as MINE, then click **对比版本** (compare versions). Expand entries in the left tree to inspect property changes; the right panes show line differences.

### Merge three revisions

1. Select the common ancestor as BASE, your changes as MINE, and the other changes as THEIRS.
2. Choose an output file and click **分析三方合并** (analyze three-way merge).
3. Review automatic results and choose BASE, MINE, or THEIRS for each conflict.
4. Use `BASE ↔ 合并结果` in the diff tab to review the proposed merged result.
5. Save once all conflicts are resolved and basic validation passes. Open the result in XD, inspect it, and save it there before marking the conflict resolved in TortoiseSVN.

SVN temporary filenames such as `.r123` and `.mine` are accepted: files are identified by their archive contents. The tool does not run `svn resolve` or commit to a repository.

### Manual TortoiseSVN integration

The installer registers commands automatically. For a portable installation, open TortoiseSVN Settings → External Programs → the appropriate tool's Advanced dialog, and add an entry for `.xd`. Replace the EXE path below.

Diff command:

```text
"D:\Tools\XD-SVN-Tools\XD-SVN-Tools.exe" diff --base "%base" --mine "%mine"
```

Merge command:

```text
"D:\Tools\XD-SVN-Tools\XD-SVN-Tools.exe" merge --base "%base" --mine "%mine" --theirs "%theirs" --merged "%merged"
```

The portable package also includes `Register-TortoiseSVN.ps1`; use `-Uninstall` to restore its previous settings. Keep the portable folder in the same location after registration. If a binary-diff entry point does not launch the configured tool, export the revisions and pass their paths manually.

## Command line

```powershell
# Export JSON structures from an XD archive
python xd_svn.py extract design.xd design.json

# Analyze without opening the GUI or writing a merged XD file
python xd_svn.py check --base base.xd --mine mine.xd --theirs theirs.xd --report report.json
```

The packaged EXE accepts the same subcommands. `check` returns `0` for no conflicts/reference errors, `1` for conflicts or reference errors, and `2` for invalid input or runtime errors. Reports include automatic merges, conflict paths, and validation errors. The GUI merge returns `0` after saving and `1` when canceled.

## Local development and builds

Use Windows x64, Python 3.14 from the official Windows distribution with Tcl/Tk, and the .NET Framework C# compiler. CI uses Python 3.14.4 on `windows-2022`.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt

# Run from source
.\.venv\Scripts\python.exe xd_svn.py

# Test, package, and smoke-check the frozen EXE
.\scripts\build-windows.ps1 -Python .\.venv\Scripts\python.exe
```

Artifacts are written to `artifacts/`, with intermediate files in `.build/`; both are ignored by Git. Building does not install the app, change SVN settings, or access production repositories.

To run tests separately:

```powershell
python -m unittest discover -v
```

The single version source is [`VERSION`](VERSION). The app reads it, and the build script uses it for the installer version and output names.

## GitHub Actions

The [`build-windows.yml`](.github/workflows/build-windows.yml) workflow runs on:

- Pushes to `main`.
- Pull requests targeting `main`.
- `v*` tags, which must match `VERSION`, for example `v0.1.3`.
- Manual **Run workflow** requests on the Actions page.

It runs tests, builds the app and installer, and checks the frozen command-line entry point. Downloads are uploaded to the run's Artifacts section and retained for 30 days. The workflow does not create GitHub Releases or publish to PyPI. It requires only repository read permission and no additional secrets.

## Merge rules and limitations

- Only ZIP-based local `.xd` documents are supported; cloud `.xdc` documents are not.
- Object properties are compared three ways. Arrays are matched by ID only when every element has a unique string `id`; other arrays are treated as a whole.
- Layer order is preserved. Different structural changes on both sides require a whole-array choice.
- Cached previews and other binary entries may also require conflict resolution. PNG previews are read from the archive and can be stale; the tool does not render the XD canvas.
- Validation covers ZIP integrity, strict JSON, required entries, and some known references. It does not guarantee complete XD semantics. Complex component states, plugin data, linked resources, and cross-version merges need manual verification.
- Prefer the same XD version on both sides. Archive limits are 256 MiB per uncompressed entry and 1 GiB total.
- Text display is capped at two million characters, with at most 5,000 property changes listed per archive entry. Merging still uses the complete data.

## License and acknowledgments

This project uses the [MIT License](LICENSE). Its extraction and merge approach was informed by [xd-scenegraph-toolkit](https://github.com/dilitirio/xd-scenegraph-toolkit) and [git-xd-merge](https://github.com/theseion/git-xd-merge). Upstream and runtime notices are in [`THIRD_PARTY_NOTICES.txt`](THIRD_PARTY_NOTICES.txt) and [`licenses/`](licenses).
