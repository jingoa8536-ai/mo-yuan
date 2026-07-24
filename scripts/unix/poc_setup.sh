#!/usr/bin/env bash
# =============================================================================
# PoC environment initialization script for the Architecture School.
# Based on docs/POC_LIVING_RUNTIME.md tech selection.
#
# Usage:
#   ./scripts/poc_setup.sh              # full setup
#   ./scripts/poc_setup.sh --skip-rust   # skip Rust toolchain setup
#   ./scripts/poc_setup.sh --skip-python # skip Python env setup
#   ./scripts/poc_setup.sh --smoke-test   # run smoke tests only
#
# Reference: docs/POC_LIVING_RUNTIME.md (§4 Technology Selection)
# Compatible with: bash 4+ (Linux, macOS, WSL)
# For Windows PowerShell version: see scripts/poc_setup.ps1
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
POC_DIR="$PROJECT_ROOT/poc"
VENV_DIR="$PROJECT_ROOT/.venv"
DAG_SCRIPT="$POC_DIR/design_physics_dag.py"
ANALYSIS_SCRIPT="$POC_DIR/dag_intervention_analysis.py"

SKIP_RUST=0
SKIP_PYTHON=0
SMOKE_ONLY=0

for arg in "$@"; do
    case "$arg" in
        --skip-rust)   SKIP_RUST=1 ;;
        --skip-python) SKIP_PYTHON=1 ;;
        --smoke-test)  SMOKE_ONLY=1 ;;
        *) echo "Unknown argument: $arg" >&2; exit 1 ;;
    esac
done

echo ""
echo "============================================================"
echo " Architecture School - PoC Environment Setup"
echo " Based on docs/POC_LIVING_RUNTIME.md (Tech Selection v0.1)"
echo "============================================================"
echo " Project root: $PROJECT_ROOT"

ok()    { echo "  [OK] $*"; }
warn()  { echo "  [!]  $*"; }
fail()  { echo "  [X]  $*" >&2; exit 1; }
step()  { echo ""; echo "====> $*"; }

# =============================================================================
# Step 1: Rust toolchain
# =============================================================================

if [[ $SMOKE_ONLY -eq 0 && $SKIP_RUST -eq 0 && $SKIP_PYTHON -eq 0 ]]; then
    step "Step 1: Verify Rust toolchain"

    if command -v rustc >/dev/null 2>&1; then
        ok "Rust toolchain present: $(rustc --version)"
    else
        warn "Rust toolchain not found. Installing via rustup..."
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable --profile minimal
        # shellcheck disable=SC1090
        source "$HOME/.cargo/env"
        ok "Rust toolchain installed: $(rustc --version)"
    fi

    if command -v cargo >/dev/null 2>&1; then
        ok "Cargo present: $(cargo --version)"
    else
        fail "Cargo not on PATH. Open a new shell and re-run."
    fi

    echo "  Note: Rust crates (sled, sha2, tokio, axum, tracing) will be"
    echo "        downloaded on first 'cargo build' in poc/living_cell/."
fi

# =============================================================================
# Step 2: Python environment
# =============================================================================

if [[ $SMOKE_ONLY -eq 0 && $SKIP_RUST -eq 0 && $SKIP_PYTHON -eq 0 ]]; then
    step "Step 2: Verify Python environment"

    USE_UV=0
    if command -v uv >/dev/null 2>&1; then
        ok "uv present: $(uv --version)"
        USE_UV=1
    else
        warn "uv not found; falling back to standard venv + pip."
    fi

    command -v python >/dev/null 2>&1 || fail "Python not found on PATH. Install Python 3.10+ and re-run."
    ok "Python: $(python --version)"

    if [[ ! -d "$VENV_DIR" ]]; then
        echo "  Creating virtual environment at $VENV_DIR ..."
        if [[ $USE_UV -eq 1 ]]; then
            uv venv "$VENV_DIR"
        else
            python -m venv "$VENV_DIR"
        fi
        ok "Virtual environment created."
    else
        ok "Virtual environment already exists at $VENV_DIR"
    fi

    VENV_PYTHON="$VENV_DIR/bin/python"
    [[ -f "$VENV_PYTHON" ]] || VENV_PYTHON="$VENV_DIR/Scripts/python.exe"
    [[ -f "$VENV_PYTHON" ]] || fail "Cannot find Python interpreter in venv at $VENV_DIR"

    ok "Venv Python: $VENV_PYTHON"
    "$VENV_PYTHON" --version

    echo "  Upgrading pip..."
    "$VENV_PYTHON" -m pip install --upgrade pip --quiet

    echo "  Installing Python dependencies (this may take a minute)..."
    DEPS=(
        regex lxml cssselect tree-sitter tree-sitter-languages
        transformers peft
        pgmpy dowhy networkx
        pytest hypothesis coverage scikit-learn
        matplotlib numpy
        opentelemetry-api opentelemetry-sdk
    )
    "$VENV_PYTHON" -m pip install --quiet "${DEPS[@]}"
    ok "Python dependencies installed."
fi

# =============================================================================
# Step 3: Verify PoC directory structure
# =============================================================================

if [[ $SMOKE_ONLY -eq 0 ]]; then
    step "Step 3: Verify PoC directory structure"

    [[ -d "$POC_DIR" ]] || mkdir -p "$POC_DIR"
    ok "poc/ directory present: $POC_DIR"

    [[ -f "$DAG_SCRIPT" ]] || fail "design_physics_dag.py MISSING at $DAG_SCRIPT"
    ok "design_physics_dag.py present."

    RUST_POC_DIR="$POC_DIR/living_cell"
    CARGO_TOML="$RUST_POC_DIR/Cargo.toml"
    if [[ ! -d "$RUST_POC_DIR" ]]; then
        warn "Creating poc/living_cell/ Rust workspace skeleton."
        mkdir -p "$RUST_POC_DIR/src"

        cat > "$CARGO_TOML" <<'EOF'
[package]
name = "laap-living-cell"
version = "0.1.0"
edition = "2021"
description = "Living Cell runtime - Architecture School PoC"
license = "MIT"

[dependencies]
sled = "0.34"
sha2 = "0.10"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
tokio = { version = "1", features = ["full"] }
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["json", "env-filter"] }
anyhow = "1"
thiserror = "1"
axum = "0.7"
EOF

        cat > "$RUST_POC_DIR/src/lib.rs" <<'EOF'
//! laap-living-cell: Living Cell runtime PoC
pub mod mind;
pub mod body;
pub mod cognbus;

pub fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}
EOF

        cat > "$RUST_POC_DIR/src/main.rs" <<'EOF'
//! Minimal Living Cell entry point.
fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env()
            .add_directive("laap_living_cell=info".parse().unwrap()))
        .json()
        .init();
    tracing::info!(event = "cell.born", version = laap_living_cell::version(), "Living Cell starting");
    tracing::info!(event = "cell.ready", "Living Cell entered idle state");
}
EOF

        for mod in mind body cognbus; do
            echo "//! $mod module placeholder." > "$RUST_POC_DIR/src/$mod.rs"
        done

        ok "Rust workspace skeleton created at $RUST_POC_DIR"
    else
        ok "Rust workspace already exists at $RUST_POC_DIR"
    fi

    if command -v cargo >/dev/null 2>&1; then
        echo "  Running 'cargo check' on living_cell ..."
        (cd "$RUST_POC_DIR" && cargo check --quiet 2>&1 || warn "cargo check returned non-zero (may need internet for first build).")
    fi
fi

# =============================================================================
# Step 4: Smoke tests
# =============================================================================

step "Step 4: Run smoke tests"

if [[ -d "$VENV_DIR" ]]; then
    VENV_PYTHON="$VENV_DIR/bin/python"
    [[ -f "$VENV_PYTHON" ]] || VENV_PYTHON="$VENV_DIR/Scripts/python.exe"
    [[ -f "$VENV_PYTHON" ]] || VENV_PYTHON="python"
else
    VENV_PYTHON="python"
fi

[[ -f "$DAG_SCRIPT" ]] || fail "Cannot run smoke test - design_physics_dag.py not found."

echo "  Running design_physics_dag.py ..."
"$VENV_PYTHON" "$DAG_SCRIPT"
ok "design_physics_dag.py smoke test PASSED."

if [[ -f "$ANALYSIS_SCRIPT" ]]; then
    echo "  Running dag_intervention_analysis.py ..."
    "$VENV_PYTHON" "$ANALYSIS_SCRIPT" || warn "dag_intervention_analysis.py returned non-zero."
fi

# =============================================================================
# Step 5: Summary
# =============================================================================

step "Setup complete"

echo "  PoC environment status:"
echo "    Rust toolchain:    $(command -v rustc >/dev/null && echo OK || echo MISSING)"
echo "    Cargo:             $(command -v cargo >/dev/null && echo OK || echo MISSING)"
echo "    Python venv:       $([[ -d "$VENV_DIR" ]] && echo OK || echo MISSING)"
echo "    poc/ directory:    $([[ -d "$POC_DIR" ]] && echo OK || echo MISSING)"
echo "    design_physics_dag.py: $([[ -f "$DAG_SCRIPT" ]] && echo OK || echo MISSING)"
echo "    Rust workspace:    $([[ -f "$CARGO_TOML" ]] && echo OK || echo MISSING)"
echo ""
echo "  Next steps:"
echo "    1. Activate venv:    source .venv/bin/activate"
echo "    2. Run DAG analysis: python poc/dag_intervention_analysis.py"
echo "    3. Build Rust cell:  cd poc/living_cell && cargo run --release"
echo "    4. Read manifesto:   less ARCHITECTURE_SCHOOL_MANIFESTO.md"
echo "    5. Read PoC spec:    less docs/POC_LIVING_RUNTIME.md"
echo ""
echo "============================================================"
echo " PoC environment ready."
echo "============================================================"
echo ""
