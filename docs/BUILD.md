# Windows build notes

The same `scripts/build-windows.ps1` is used locally and in GitHub Actions.

1. Read and validate `VERSION` (and the tag name for tag builds).
2. Run the standard-library unit and Tk GUI state tests.
3. Package the app with PyInstaller, including the version file and Tcl/Tk.
4. Include source, README files, integration script, and licenses.
5. Replace the version placeholder in a temporary copy of `installer/Setup.cs`.
6. Compile a separate uninstaller using the .NET Framework compiler.
7. Create the portable ZIP, then embed that ZIP in the compiled installer.
8. Smoke-check the frozen executable's clean-merge and conflict reports.
9. Write SHA-256 checksums and upload artifacts in CI.

Only `VERSION` needs editing for a version change. The C# template must retain
`__APP_VERSION__`; generated source belongs in `.build/`, not in Git.

The build script never executes the installer. Installation writes to the
current user's LocalAppData and backs up the affected TortoiseSVN settings.
Uninstallation and upgrade checks should be performed in a disposable Windows
account or VM when changing installer behavior.

Action versions are pinned to commit SHAs. Builds have read-only repository
permission. On a matching version-tag push, a separate job downloads the tested
artifacts and publishes a release with the built-in GITHUB_TOKEN and contents:
write permission. It uses fixed asset names for permanent latest-download URLs,
regenerates matching checksums, uploads to a draft, then publishes it. Published
assets are not replaced on reruns. Pull-request builds cannot publish releases.
