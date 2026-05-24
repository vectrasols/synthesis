# Synthesis Suite

**A professional desktop data analysis and machine-learning workbench**

Synthesis Suite is an open-source desktop application for data scientists, analysts, and engineers built with Electron, FastAPI, pandas, scikit-learn, and Plotly.

<div align="center">

![Synthesis Suite Main Interface](assets/screenshot_visualize.png)

![Synthesis Suite Prepare Interface](assets/screenshot_prepare.png)
</div>

### Key Features

- **Data Import**: CSV, Excel, JSON, TSV, Parquet, URL, clipboard, manual, and sample dataset support
- **Visualization**: Interactive 2D and 3D Plotly charts with export capabilities
- **Data Cleaning**: Missing-value handling, outlier removal, dtype conversion, scaling, binarization, and encoding
- **Feature Engineering**: Feature selection and extraction tools
- **Machine Learning**: Supervised, unsupervised, semi-supervised, anomaly-detection, ensemble, and reinforcement-learning algorithm demonstrations
- **Local Backend**: FastAPI server spawned by Electron for secure, offline data processing

## Prerequisites

### System Requirements
- **Node.js**: 22 or newer
- **Python**: 3.11 or newer
- **npm**: 8 or newer
- **Git**: 2.0 or newer

### Optional
- **Conda**: for advanced environment management (standard Python virtual environment recommended)

## Getting Started

### For Users

Download the latest installer from [GitHub Releases](https://github.com/your-org/synthesis-suite/releases):
- **Windows**: `synthesis-suite-setup-x.x.x.exe`
- **macOS**: `synthesis-suite-x.x.x.dmg` or `synthesis-suite-x.x.x.zip`
- **Linux**: `synthesis-suite-x.x.x.AppImage`, `.deb`, or `.rpm`

#### ⚠️ Security Warnings on First Launch

**Windows Users:**
> When you first run the installer, Microsoft Defender SmartScreen may display a warning stating the publisher is unknown.
> 1. Click **"More info"**
> 2. Click **"Run anyway"**
> 
> This warning appears because Synthesis Suite is not code-signed. Download only from the [official GitHub releases](https://github.com/your-org/synthesis-suite/releases).

**macOS Users:**
> macOS Gatekeeper may block the application on first launch with a security warning.
> 1. **Close** the warning dialog
> 2. Open **System Settings** → **Privacy & Security**
> 3. Scroll down to **Security** section
> 4. Find the Synthesis Suite entry and click **"Open Anyway"**
> 5. **Enter your Mac password** to permanently trust the application
> 
> You only need to do this once. Future launches will open normally.

### For Contributors

#### Setup Development Environment

**Linux/macOS:**
```bash
git clone https://github.com/your-org/synthesis-suite.git
cd synthesis-suite
npm install
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
npm run setup:backend
npm start
```

**Windows (PowerShell):**
```powershell
git clone https://github.com/your-org/synthesis-suite.git
cd synthesis-suite
npm install
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
npm run setup:backend
npm start
```

#### Python Backend Resolution

During development, Electron searches for the Python backend in this order:
1. `SYNTHESIS_PYTHON` environment variable (must point to a valid Python executable)
2. `SYNTHESIS_VENV` environment variable
3. `.venv` in the project root
4. Active `VIRTUAL_ENV`
5. Active `CONDA_PREFIX`
6. Conda environment named by `SYNTHESIS_CONDA_ENV`
7. System `python3` or `python`

## Development Workflow

### Quality Checks

**Backend Smoke Tests:**
```bash
npm run smoke:backend        # Full test suite
npm run smoke:backend:quick  # Faster smoke tests
```

**Code Quality:**
```bash
npm run check:js  # TypeScript and JavaScript syntax validation
```

### Building

**For your current platform:**
```bash
npm run pack          # Quick package for local testing
npm run build:linux   # Linux (use on Linux)
npm run build:win     # Windows (use on Windows)
npm run build:mac     # macOS (use on macOS)
```

**Backend binary packaging:**
```bash
npm run build:backend  # Bundle Python backend before packaging
```

> **Note**: For production releases across all platforms, use the GitHub Actions release workflow instead of manual cross-compilation. Push a version tag `v*.*.*` and GitHub will automatically build Windows, macOS, and Linux installers in parallel.

## Project Architecture

```
synthesis-suite/
├── main/                      # Generated Electron main process
│   ├── index.js              # Main process entry point
│   ├── preload.js            # Preload script for IPC security
│   └── updater.js            # App update logic
├── src/                       # TypeScript source code
│   ├── main/                 # Electron main process source
│   └── renderer/             # UI and renderer logic
├── renderer/                 # Generated HTML/CSS/JS desktop UI
│   ├── index.html            # Main application shell
│   ├── css/                  # Application styles
│   └── js/                   # Generated JavaScript
├── python-backend/           # FastAPI backend services
│   ├── server.py             # FastAPI application
│   ├── data_service.py       # Data processing service
│   ├── chart_service.py      # Charting and visualization
│   ├── ml_service.py         # Machine learning service
│   └── requirements.txt      # Python dependencies
├── scripts/                  # Build and utility scripts
├── .github/workflows/        # CI/CD automation
└── assets/                   # Icons and build resources
```

### Technology Stack

- **Frontend**: Electron, TypeScript, Plotly.js
- **Backend**: FastAPI, pandas, scikit-learn, NumPy, SciPy
- **Build**: npm, webpack
- **CI/CD**: GitHub Actions

## Contributing

We welcome contributions from the community! Please review our [CONTRIBUTING.md](CONTRIBUTING.md) guidelines before opening an issue or pull request.

### How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Running Tests Before Submitting

```bash
npm run check:js           # Lint and type-check
npm run smoke:backend      # Run backend tests
```

## Security

This project is unsigned and for development/community use. See [SECURITY.md](SECURITY.md) for details on reporting vulnerabilities.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

**[More information](https://github.com/your-org/synthesis-suite)** | **[Report an Issue](https://github.com/your-org/synthesis-suite/issues)** | **[Code of Conduct](CODE_OF_CONDUCT.md)**
