# Security Report

## Executive Summary
- Automated scans were attempted but constrained by network restrictions and missing tooling.
- Manual inspection revealed hard-coded credentials and secret keys within the repository.
- GitHub Actions workflows were added for CodeQL and Semgrep to enable future continuous scanning.

## Findings
### High
- `.env` file in repository contains SMTP credentials and application secret key.
- `app/modules/license_utils.py` embeds a hard-coded Fernet secret key.

### Medium
- `config.py` uses a default `SECRET_KEY` fallback if environment variable is unset.

## Dependency Audit
- `pip-audit` could not complete due to platform-specific dependency `pywin32`.

## Static Analysis
- Semgrep and CodeQL scans could not run locally due to proxy restrictions and missing query packs.

## Recommendations
- Remove `.env` from version control; load secrets from environment or secret manager.
- Rotate exposed SMTP credentials and Fernet key immediately.
- Require a strong `SECRET_KEY` via configuration and avoid hard-coded defaults.
- Review dependencies and run `pip-audit` in an environment with Windows packages available.
- Once network access is available, run Semgrep and CodeQL to identify additional vulnerabilities.
