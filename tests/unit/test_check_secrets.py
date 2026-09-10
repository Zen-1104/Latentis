# tests/unit/test_check_secrets.py
# Unit and adversarial tests for scripts/check_secrets.sh (Gate: INV-10)

import subprocess
from pathlib import Path

import pytest

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_secrets.sh"


@pytest.mark.fast
def test_check_secrets_help() -> None:
    """Verify check_secrets.sh --help exits 0 and documents Gate: INV-10."""
    result = subprocess.run(
        [str(SCRIPT_PATH), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "INV-10" in result.stdout
    assert "Usage:" in result.stdout


@pytest.mark.fast
def test_check_secrets_clean_repo() -> None:
    """Verify check_secrets.sh returns 0 on the clean repository."""
    result = subprocess.run(
        [str(SCRIPT_PATH)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "INV-10 secret scan passed" in result.stdout


@pytest.mark.fast
def test_detect_aws_access_key(tmp_path: Path) -> None:
    """Verify detection of AWS Access Key ID and that secret value is masked."""
    # Constructed dynamically to avoid embedding raw patterns
    test_file = tmp_path / "aws_leak.txt"
    fake_key = "AK" + "IA" + "1234567890ABCDEF"
    test_file.write_text(f"access_key = '{fake_key}'\n")

    result = subprocess.run(
        [str(SCRIPT_PATH), str(test_file)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "GATE FAILURE: INV-10" in result.stdout
    assert "aws-access-key-id" in result.stdout
    # Invariant: the matched secret value itself must NEVER be echoed in stdout
    assert fake_key not in result.stdout


@pytest.mark.fast
def test_detect_private_key(tmp_path: Path) -> None:
    """Verify detection of RSA/EC private key headers."""
    test_file = tmp_path / "id_rsa"
    header = "-----" + "BEGIN RSA PRIVATE KEY" + "-----"
    test_file.write_text(f"{header}\nMIIEowIBAAKCAQEA0...\n")

    result = subprocess.run(
        [str(SCRIPT_PATH), str(test_file)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "private-key" in result.stdout


@pytest.mark.fast
def test_detect_github_token(tmp_path: Path) -> None:
    """Verify detection of GitHub personal access tokens."""
    test_file = tmp_path / "github.txt"
    token = "gh" + "p_" + "1234567890abcdefghijklmnopqrstuvwxyz1234"
    test_file.write_text(f"GITHUB_TOKEN = '{token}'\n")

    result = subprocess.run(
        [str(SCRIPT_PATH), str(test_file)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "github-token" in result.stdout
    assert token not in result.stdout


@pytest.mark.fast
def test_detect_connection_string_with_password(tmp_path: Path) -> None:
    """Verify detection of database connection strings with credentials."""
    test_file = tmp_path / "db_config.py"
    conn_str = "postgres" + "://" + "admin:SuperSecretPass123!@localhost:5432/latentis"
    test_file.write_text(f"DB_URL = '{conn_str}'\n")

    result = subprocess.run(
        [str(SCRIPT_PATH), str(test_file)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "db-connection-string" in result.stdout
    assert "SuperSecretPass123!" not in result.stdout


@pytest.mark.fast
def test_detect_unencrypted_env_file(tmp_path: Path) -> None:
    """Verify detection of unencrypted .env files."""
    env_file = tmp_path / ".env"
    env_file.write_text("SOME_VAR=value\n")

    result = subprocess.run(
        [str(SCRIPT_PATH), str(env_file)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "unencrypted-env-file" in result.stdout


@pytest.mark.fast
def test_ignore_placeholders_and_templates(tmp_path: Path) -> None:
    """Verify placeholder credentials in templates do not trigger false positives."""
    clean_file = tmp_path / "sample_config.py"
    clean_file.write_text(
        "password = '<password>'\n"
        "api_key = 'dummy'\n"
        "secret = 'placeholder'\n"
        "token = '${API_TOKEN}'\n"
    )

    result = subprocess.run(
        [str(SCRIPT_PATH), str(clean_file)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "INV-10 secret scan passed" in result.stdout


@pytest.mark.fast
@pytest.mark.adversarial
def test_adversarial_ignore_directive(tmp_path: Path) -> None:
    """Verify line-level ignore directive allows deliberate test cases."""
    test_file = tmp_path / "whitelisted_test.py"
    fake_key = "AK" + "IA" + "9999999999ZZZZZZ"
    test_file.write_text(f"TEST_KEY = '{fake_key}'  # secret-scan: ignore\n")

    result = subprocess.run(
        [str(SCRIPT_PATH), str(test_file)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
