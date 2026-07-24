<#
.SYNOPSIS
    PoC environment initialization script for the Architecture School.
    Based on docs/POC_LIVING_RUNTIME.md tech selection.

.DESCRIPTION
    Initializes Rust + Python environments for running the Living Runtime PoC.
    Verifies toolchains, installs dependencies, runs smoke tests.

.EXAMPLE
    .\scripts\poc_setup.ps1
    .\scripts\poc_setup.ps1 -SkipRust    # Skip Rust toolchain setup
    .\scripts\poc_setup.ps1 -SkipPython  # Skip Python environment setup
    .\scripts\poc_setup.ps1 -SmokeTest   # Run smoke tests only

.PARAMETER SkipRust
    Skip Rust toolchain verification and initialization.

.PARAMETER SkipPython
    Skip Python virtual environment creation and dependency installation.

.PARAMETER SmokeTest
    Run only the smoke tests (assumes environment is already set up).

.NOTES
    Reference: docs/POC_LIVING_RUNTIME.md (§4 Technology Selection)
    Compatible with: PowerShell 7+ (Windows)
    For cross-platform bash version: see scripts/poc_setup.sh
#>

[CmdletBinding()]
param(
    [switch]$SkipRust,
    [switch]$SkipPython,
    [switch]$SmokeTest
)

$ErrorActionPreference = "Stop"
$VerbosePreference = "Continue"

# =============================================================================
# Helper functions
# =============================================================================

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "====> $Message" -ForegroundColor Cyan
}

function Write-OK {
    param([string]$Message)
    Write-Host "  [OK] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "  [!]  $Message" -ForegroundColor Yellow
}

function Write-Err {
    param([string]$Message)
    Write-Host "  [X]  $Message" -ForegroundColor Red
}

function Test-Command {
    param([string]$Name)
    return [bool](Get-Command -Name $Name -ErrorAction SilentlyContinue)
}

function Invoke-Safe {
    param([scriptblock]$Block, [string]$Description)
    try {
        & $Block
        if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne $null) {
            throw "$Description failed with exit code $LASTEXITCODE"
        }
    } catch {
        Write-Err "$Description`: $_"
        throw
    }
}

# =============================================================================
# Project paths
# =============================================================================

$ProjectRoot = Resolve-Path "$PSScriptRoot/.."
$PocDir = Join-Path $ProjectRoot "poc"
$VenvDir = Join-Path $ProjectRoot ".venv"
$DagScript = Join-Path $PocDir "design_physics_dag.py"
$AnalysisScript = Join-Path $PocDir "dag_intervention_analysis.py"

Write-Host ""
Write-Host "============================================================" -ForegroundColor DarkGray
Write-Host " Architecture School - PoC Environment Setup" -ForegroundColor White
Write-Host " Based on docs/POC_LIVING_RUNTIME.md (Tech Selection v0.1)" -ForegroundColor DarkGray
Write-Host "============================================================" -ForegroundColor DarkGray
Write-Host " Project root: $ProjectRoot" -ForegroundColor DarkGray

# =============================================================================
# Step 1: Rust toolchain
# =============================================================================

if (-not $SkipPython -and -not $SkipRust -and -not $SmokeTest) {

    Write-Step "Step 1: Verify Rust toolchain"

    if (Test-Command "rustc") {
        $rustVer = rustc --version
        Write-OK "Rust toolchain present: $rustVer"
    } else {
        Write-Warn "Rust toolchain not found. Installing via rustup..."
        Invoke-Safe -Description "rustup install" -Block {
            # Download rustup-init.exe and run
            $rustupUrl = "https://win.rustup.rs/x86_64"
            $rustupInit = Join-Path $env:TEMP "rustup-init.exe"
            Invoke-WebRequest -Uri $rustupUrl -OutFile $rustupInit -UseBasicParsing
            & $rustupInit -y --default-toolchain stable --profile minimal
            # Update PATH for current session
            $cargoHome = if ($env:CARGO_HOME) { $env:CARGO_HOME } else { "$env:USERPROFILE\.cargo" }
            $env:PATH = "$cargoHome\bin;$env:PATH"
            [Environment]::SetEnvironmentVariable("PATH", "$cargoHome\bin;$env:PATH", "User")
        }
        Write-OK "Rust toolchain installed: $(rustc --version)"
    }

    if (Test-Command "cargo") {
        Write-OK "Cargo present: $(cargo --version)"
    } else {
        Write-Err "Cargo not on PATH. Open a new shell and re-run."
        exit 1
    }

    # Verify key Rust crates are available (will be downloaded on first build)
    Write-Host "  Note: Rust crates (sled, sha2, tokio, axum, tracing) will be"
    Write-Host "        downloaded on first 'cargo build' in poc/living_cell/."
}

# =============================================================================
# Step 2: Python environment
# =============================================================================

if (-not $SkipRust -and -not $SkipPython -and -not $SmokeTest) {

    Write-Step "Step 2: Verify Python environment"

    # Prefer 'uv' (fast), fall back to standard venv
    $useUv = $false
    if (Test-Command "uv") {
        Write-OK "uv present: $(uv --version)"
        $useUv = $true
    } else {
        Write-Warn "uv not found; falling back to standard venv + pip."
    }

    if (-not (Test-Command "python")) {
        Write-Err "Python not found on PATH. Install Python 3.10+ and re-run."
        exit 1
    }

    $pyVer = python --version 2>&1
    Write-OK "Python: $pyVer"

    # Create / refresh virtual environment
    if (-not (Test-Path $VenvDir)) {
        Write-Host "  Creating virtual environment at $VenvDir ..."
        if ($useUv) {
            Invoke-Safe -Description "uv venv" -Block { uv venv $VenvDir }
        } else {
            Invoke-Safe -Description "python -m venv" -Block { python -m venv $VenvDir }
        }
        Write-OK "Virtual environment created."
    } else {
        Write-OK "Virtual environment already exists at $VenvDir"
    }

    # Activate the venv for the rest of this script
    $VenvPython = Join-Path $VenvDir "Scripts\python.exe"
    if (-not (Test-Path $VenvPython)) {
        $VenvPython = Join-Path $VenvDir "bin\python"
    }

    if (-not (Test-Path $VenvPython)) {
        Write-Err "Cannot find Python interpreter in venv at $VenvDir"
        exit 1
    }

    Write-OK "Venv Python: $VenvPython"
    & $VenvPython --version

    # Upgrade pip
    Write-Host "  Upgrading pip..."
    Invoke-Safe -Description "pip upgrade" -Block {
        & $VenvPython -m pip install --upgrade pip --quiet
    }

    # Install Python dependencies per docs/POC_LIVING_RUNTIME.md §4.2 / §4.3
    Write-Host "  Installing Python dependencies (this may take a minute)..."

    $deps = @(
        # L1 Perception: regex / lxml / cssselect / tree-sitter
        "regex",
        "lxml",
        "cssselect",
        "tree-sitter",
        "tree-sitter-languages",
        # L2 Memory: transformers + peft (LoRA)
        "transformers",
        "peft",
        # L3 Reasoning: pgmpy + doWhy + NetworkX
        "pgmpy",
        "dowhy",
        "networkx",
        # L4-L7: pytest + hypothesis + coverage + scikit-learn
        "pytest",
        "hypothesis",
        "coverage",
        "scikit-learn",
        # Visualization (for figures)
        "matplotlib",
        "numpy",
        # Observability
        "opentelemetry-api",
        "opentelemetry-sdk"
    )

    foreach ($dep in $deps) {
        Write-Host "    - $dep"
    }

    Invoke-Safe -Description "pip install dependencies" -Block {
        & $VenvPython -m pip install --quiet $deps
    }
    Write-OK "Python dependencies installed."
}

# =============================================================================
# Step 3: Initialize PoC directory structure
# =============================================================================

if (-not $SmokeTest) {

    Write-Step "Step 3: Verify PoC directory structure"

    if (-not (Test-Path $PocDir)) {
        Write-Warn "Creating poc/ directory."
        New-Item -ItemType Directory -Path $PocDir -Force | Out-Null
    }
    Write-OK "poc/ directory present: $PocDir"

    if (Test-Path $DagScript) {
        Write-OK "design_physics_dag.py present."
    } else {
        Write-Err "design_physics_dag.py MISSING at $DagScript"
        exit 1
    }

    # Create Rust workspace skeleton if missing
    $rustPocDir = Join-Path $PocDir "living_cell"
    $cargoToml = Join-Path $rustPocDir "Cargo.toml"
    if (-not (Test-Path $rustPocDir)) {
        Write-Warn "Creating poc/living_cell/ Rust workspace skeleton."
        New-Item -ItemType Directory -Path "$rustPocDir\src" -Force | Out-Null

        # Write a minimal Cargo.toml per docs/POC_LIVING_RUNTIME.md §4.1
        $cargoContent = @"
[package]
name = "laap-living-cell"
version = "0.1.0"
edition = "2021"
description = "Living Cell runtime - Architecture School PoC"
license = "MIT"

[dependencies]
# Mind Layer: embedded KV store + zero-copy columnar state
sled = "0.34"
apache-arrow = { version = ">=50", optional = true }
# Memory addressing & serialization
sha2 = "0.10"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
# Async runtime
tokio = { version = "1", features = ["full"] }
# Observability
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["json", "env-filter"] }
# Error handling
anyhow = "1"
thiserror = "1"
# HTTP server (for cell control API)
axum = "0.7"

[features]
default = ["arrow"]
arrow = ["dep:apache-arrow"]
"@
        Set-Content -Path $cargoToml -Value $cargoContent -Encoding UTF8

        # Write a minimal lib.rs
        $libRs = @"
//! laap-living-cell: Living Cell runtime PoC
//!
//! See docs/POC_LIVING_RUNTIME.md for the architecture specification.

pub mod mind;
pub mod body;
pub mod cognbus;

pub fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}
"@
        Set-Content -Path "$rustPocDir\src\lib.rs" -Value $libRs -Encoding UTF8

        # Write a minimal main.rs
        $mainRs = @"
//! Minimal Living Cell entry point.
//! Logs the launch event sequence per ARCHITECTURE_SCHOOL_MANIFESTO.md Appendix A.

use laap_living_cell::version;

fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env()
            .add_directive("laap_living_cell=info".parse().unwrap()))
        .with_writer(std::io::stdout)
        .json()
        .init();

    tracing::info!(event = "cell.born", version = version(), "Living Cell starting");
    tracing::info!(event = "mind.state_loaded", snapshot_hash = "genesis", "Mind Layer initialized");
    tracing::info!(event = "body.spawned", runtime = "minimal", host = std::env::consts::ARCH, "Body Layer spawned");
    tracing::info!(event = "alignment.guard_activated", policy_version = "0.1.0", "AlignmentGuard active");
    tracing::info!(event = "cell.ready", "Living Cell entered idle state");
}
"@
        Set-Content -Path "$rustPocDir\src\main.rs" -Value $mainRs -Encoding UTF8

        # Write placeholder modules
        foreach ($mod in @("mind", "body", "cognbus")) {
            $modContent = "//! `$mod` module placeholder. See docs/POC_LIVING_RUNTIME.md §3.`n"
            Set-Content -Path "$rustPocDir\src\$mod.rs" -Value $modContent -Encoding UTF8
        }

        Write-OK "Rust workspace skeleton created at $rustPocDir"
    } else {
        Write-OK "Rust workspace already exists at $rustPocDir"
    }

    # Verify Rust workspace compiles (cargo check)
    if (Test-Command "cargo") {
        Write-Host "  Running 'cargo check' on living_cell ..."
        Push-Location $rustPocDir
        try {
            & cargo check --quiet 2>&1 | Out-Host
            if ($LASTEXITCODE -eq 0) {
                Write-OK "Rust workspace compiles cleanly."
            } else {
                Write-Warn "Rust 'cargo check' returned $LASTEXITCODE (may need internet for first build)."
            }
        } finally {
            Pop-Location
        }
    } else {
        Write-Warn "cargo not available; skipping Rust compile check."
    }
}

# =============================================================================
# Step 4: Smoke tests
# =============================================================================

Write-Step "Step 4: Run smoke tests"

# Determine which Python to use
$Python = if ($VenvDir -and (Test-Path $VenvDir)) {
    $p = Join-Path $VenvDir "Scripts\python.exe"
    if (Test-Path $p) { $p } else { Join-Path $VenvDir "bin\python" }
} else {
    "python"
}

if (-not (Test-Path $DagScript)) {
    Write-Err "Cannot run smoke test - design_physics_dag.py not found."
    exit 1
}

Write-Host "  Running design_physics_dag.py ..."
& $Python $DagScript 2>&1 | Out-Host
$exitCode = $LASTEXITCODE
if ($exitCode -eq 0) {
    Write-OK "design_physics_dag.py smoke test PASSED (exit 0)."
} else {
    Write-Err "design_physics_dag.py smoke test FAILED (exit $exitCode)."
    exit $exitCode
}

# Run the comprehensive analysis script if present
if (Test-Path $AnalysisScript) {
    Write-Host "  Running dag_intervention_analysis.py ..."
    & $Python $AnalysisScript 2>&1 | Out-Host
    $exitCode = $LASTEXITCODE
    if ($exitCode -eq 0) {
        Write-OK "dag_intervention_analysis.py PASSED (exit 0)."
    } else {
        Write-Warn "dag_intervention_analysis.py returned exit $exitCode."
    }
}

# =============================================================================
# Step 5: Summary
# =============================================================================

Write-Step "Setup complete"

$summary = @()
$summary += "PoC environment status:"
$summary += "  Rust toolchain:    $(if (Test-Command 'rustc') { 'OK' } else { 'MISSING' })"
$summary += "  Cargo:             $(if (Test-Command 'cargo') { 'OK' } else { 'MISSING' })"
$summary += "  Python venv:       $(if (Test-Path $VenvDir) { 'OK' } else { 'MISSING' })"
$summary += "  poc/ directory:    $(if (Test-Path $PocDir) { 'OK' } else { 'MISSING' })"
$summary += "  design_physics_dag.py: $(if (Test-Path $DagScript) { 'OK' } else { 'MISSING' })"
$summary += "  Rust workspace:     $(if (Test-Path $cargoToml) { 'OK' } else { 'MISSING' })"
$summary += ""
$summary += "Next steps:"
$summary += "  1. Activate venv:    .venv\Scripts\Activate.ps1"
$summary += "  2. Run DAG analysis: python poc\dag_intervention_analysis.py"
$summary += "  3. Build Rust cell:  cd poc\living_cell && cargo run --release"
$summary += "  4. Read manifesto:   ARCHITECTURE_SCHOOL_MANIFESTO.md"
$summary += "  5. Read PoC spec:    docs\POC_LIVING_RUNTIME.md"

Write-Host ""
$summary | ForEach-Object { Write-Host "  $_" -ForegroundColor White }
Write-Host ""
Write-Host "============================================================" -ForegroundColor DarkGray
Write-Host " PoC environment ready." -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor DarkGray
Write-Host ""
