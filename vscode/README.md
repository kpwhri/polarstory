# polarstory for VS Code

An optional, dependency-free VS Code extension for right-click profiling of **local `.parquet` files**. It invokes the
Python package already installed in the workspace-selected environment. It does not bundle Python or polars.

## Development / installation

Open `vscode/` in VS Code and press F5 to launch an Extension Development Host. To produce a VSIX for installation, run
`npx @vscode/vsce package` in this directory in an environment with access to the VS Code packaging tool, then run
**Extensions: Install from VSIX**.

## Commands

Right-click a parquet file in the Explorer and choose **polarstory: Inspect Parquet Metadata**, **Generate Quick
Profile**, **Generate Standard Profile**, or **Generate Full Profile**.

The extension uses the active interpreter from Microsoft's Python extension for the selected workspace. If none is
resolved, set `polarstory.pythonPath` to the full path of an interpreter with `polarstory` installed. It never guesses a
global Python installation.

Results are named `data.profile.html`, `data.profile-2.html`, etc., beside the original file; previous reports are
retained. If `polarstory.openReport` is enabled, successful reports open in the default browser. Errors appear in
**Output → polarstory**. A `polarstory.toml` in the VS Code workspace root can provide shared settings, or set
`polarstory.configFile` to a specific TOML path.

Only local files are supported in this initial version. Remote/WSL/SSH workspaces and non-Parquet file formats are not
yet verified. The extension uses Node's `spawn()` without a shell so spaces in paths are preserved.

## Tests

```bash
npm test
npm run check
```
