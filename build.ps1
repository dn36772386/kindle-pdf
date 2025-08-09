param(
  [ValidateSet('all','ui','core')]
  [string]$Target = 'all'
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path .venv)) {
  python -m venv .venv
}
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\pip install -r requirements.txt pyinstaller

if ($Target -eq 'core' -or $Target -eq 'all') {
  .\.venv\Scripts\pyinstaller --noconfirm --noconsole `
    --name Kindless `
    --manifest dpi_aware.manifest `
    --add-data "kindless.ini;." `
    kindless.py
}

if ($Target -eq 'ui' -or $Target -eq 'all') {
  .\.venv\Scripts\pyinstaller --noconfirm --noconsole `
    --name KindlessUI `
    --manifest dpi_aware.manifest `
    kindless_ui.py
}

Write-Host "Build complete. Check the dist\ folder."
