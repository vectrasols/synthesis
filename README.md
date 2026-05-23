# Synthesis Suite

Synthesis Suite is an open-source desktop data analysis and machine-learning workbench built with Electron, FastAPI, pandas, scikit-learn, and Plotly.

It supports local file import, manual/paste/URL data loading, data cleaning, interactive visualization, preprocessing, feature engineering, model training, and runnable algorithm demos.

## Highlights

- CSV, Excel, JSON, TSV, Parquet, URL, clipboard, manual, and sample dataset import
- Interactive 2D and 3D Plotly charts with export support
- Missing-value handling, outlier removal, dtype conversion, scaling, binarization, encoding, feature selection, and feature extraction
- Supervised, unsupervised, semi-supervised, anomaly-detection, ensemble, and reinforcement-learning demos
- Local FastAPI backend spawned by Electron
- Native installers for Windows, macOS, and Linux through GitHub Actions

## Installers

Installers are produced from tagged GitHub releases:

- Windows: one-click NSIS setup executable
- macOS: DMG and ZIP packages
- Linux: AppImage, DEB, and RPM packages

Create a release by pushing a version tag:

```bash
git tag v1.2.0
git push origin v1.2.0
```

The release workflow builds each installer on its matching GitHub runner. This matters because the Python backend binary is OS-specific. Building Windows, macOS, and Linux installers from one Linux machine is not reliable for this project.

Releases also publish payload update assets next to the installers:

- `payload-manifest-<platform>-<arch>.json`
- `payload-renderer-<platform>-<arch>-<version>.tgz`
- `payload-backend-<platform>-<arch>-<version>.tgz`

Users still install only the normal platform installer. Packaged apps use these payload assets for smaller renderer/backend updates, while `electron-updater` remains available for full launcher/installer updates.

## Requirements

- Node.js 22 or newer
- Python 3.11
- npm
- Git

Conda is optional. A normal Python virtual environment is the recommended path for contributors.

## Local Development

From this directory:

```bash
npm install
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
npm run setup:backend
npm start
```

On Windows PowerShell:

```powershell
npm install
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
npm run setup:backend
npm start
```

Electron resolves the Python backend in this order during development:

1. `SYNTHESIS_PYTHON`, if it points to a runnable Python executable
2. `SYNTHESIS_VENV`, if set
3. `.venv` in the project root
4. The active `VIRTUAL_ENV`
5. The active `CONDA_PREFIX`
6. Conda env named by `SYNTHESIS_CONDA_ENV`, if set
7. System `python3` or `python`

## Verification

Run the backend smoke suite:

```bash
npm run smoke:backend
```

Run a faster smoke suite:

```bash
npm run smoke:backend:quick
```

Check TypeScript and generated JavaScript syntax:

```bash
npm run check:js
```

## Packaging

Local packaging is intended for the OS you are currently using:

```bash
npm run pack
npm run build:linux
```

Use these on their matching platforms:

```bash
npm run build:win
npm run build:mac
npm run build:linux
```

The backend is bundled before Electron packaging with:

```bash
npm run build:backend
```

For all-platform releases, use the GitHub Actions release workflow instead of trying to cross-compile from Linux. Push a `v*.*.*` tag and GitHub will build Windows, macOS, and Linux artifacts in parallel.

Unsigned macOS and Windows builds may show operating-system trust warnings. Code signing and notarization can be added later with repository secrets.

## Project Structure

- `main/` - generated Electron main process, preload bridge, updater setup
- `src/` - TypeScript source for Electron and renderer logic
- `renderer/` - HTML/CSS and generated JavaScript desktop UI
- `python-backend/` - FastAPI backend and data/ML/chart services
- `scripts/` - development, Python launcher, backend build, and smoke-test scripts
- `.github/workflows/` - CI and release automation
- `assets/` - app icons and build resources

## Contributing

Issues and pull requests are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR.

## License

MIT. See [LICENSE](LICENSE).
