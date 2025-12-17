param (
    [Parameter(Mandatory = $true)]
    [ValidateSet("setup", "developer", "client")]
    [string]$Role
)
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

$VenvPath = Join-Path $ProjectRoot ".venv"
$PythonExe = Join-Path $VenvPath "Scripts\python.exe"
$PipExe = Join-Path $VenvPath "Scripts\pip.exe"

# requirements
$Requirements = Join-Path $ProjectRoot "requirements.txt"

function Setup-Venv {
    Write-Host "Setting up virtual environment."

    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Error "Python is not installed or not in PATH."
        exit 1
    }

    python -m venv $VenvPath

    if (-not (Test-Path $PipExe)) {
        Write-Error "pip not found in virtual environment."
        exit 1
    }

    Write-Host "Installing requirements."
    & $PipExe install -r $Requirements
}

# --- setup only ---
if ($Role -eq "setup") {
    Setup-Venv
    Write-Host "Setup completed."
    exit 0
}

# --- ensure venv exists ---
if (-not (Test-Path $PythonExe)) {
    Write-Host "Virtual environment not found. Running setup."
    Setup-Venv
}

switch ($Role) {
    "developer" {
        $WorkDir = Join-Path $ProjectRoot "developer"
        $Entry = "developer_client.py"
    }
    "client" {
        $WorkDir = Join-Path $ProjectRoot "client"
        $Entry = "lobby_client.py"
    }
}

Write-Host "Starting $Role from $WorkDir..."

Start-Process -FilePath $PythonExe -ArgumentList $Entry -WorkingDirectory $WorkDir -NoNewWindow -Wait