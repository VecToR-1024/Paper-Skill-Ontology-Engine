param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PythonArgs
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $PSCommandPath
$ProjectRoot = Split-Path -Parent $ScriptDir

$Candidates = @()

if ($env:PAPER_SUITE_PYTHON) {
    $Candidates += $env:PAPER_SUITE_PYTHON
}

if ($env:CONDA_PREFIX) {
    $Candidates += Join-Path $env:CONDA_PREFIX "python.exe"
}

$Candidates += Join-Path $ProjectRoot ".venv\Scripts\python.exe"

$PythonExe = $Candidates |
    Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } |
    Select-Object -First 1

if (-not $PythonExe) {
    throw "No Python interpreter found. Set PAPER_SUITE_PYTHON, activate the paper-suite Conda environment, or create .venv."
}

& $PythonExe @PythonArgs
exit $LASTEXITCODE
