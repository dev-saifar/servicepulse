# Security Assessment Report for ServicePulse

## Executive Summary
- **Project**: ServicePulse (Python/Flask)
- **Date**: 2025-08-14
- **Tools Executed**: Semgrep, pip-audit (failed), trufflehog, pytest (failed)
- **Key Risks**: Secrets committed to repo, debug mode enabled, absence of automated security scanning.

## Findings by Severity

### Critical
1. **Hardcoded credentials in `.env`** – SMTP password and other secrets are stored in the repository. This could allow unauthorized access to email services.
   - File: `.env`
   - Fix: Remove `.env` from version control, rotate credentials, and use environment variables or secret managers.

### High
1. **Debug mode enabled in production code** – Flask application runs with `DEBUG=True` and `ENV=development` which may expose sensitive information.
   - File: `app/__init__.py` lines 35-36; `run.py` line 6.
   - Fix: Use environment-specific configuration and disable debug mode in production.

2. **Default `SECRET_KEY` value** – Application falls back to a hardcoded secret key, weakening session security.
   - File: `config.py` line 6.
   - Fix: Require `SECRET_KEY` via environment variable and rotate regularly.

### Medium
1. **Unpinned dependencies** – `requirements.txt` includes a wide range of packages without verification of integrity, and contains Windows-only packages (`pywin32`) causing audit failures.
   - Fix: Use hashes/lockfiles and remove platform-specific packages.

### Low
1. **High entropy string detected in `license.lic`** – May contain encoded data or keys.
   - File: `license.lic`
   - Fix: Verify necessity of this file and remove or encrypt if it contains secrets.

## Tooling Output Summary
- **Semgrep**: 0 findings (`artifacts/semgrep.sarif`).
- **Semgrep OWASP Top 10**: 0 findings (`artifacts/semgrep-owasp.json`).
- **Trufflehog**: High-entropy strings found in `license.lic` and committed credentials in `.env` (`artifacts/secrets.json`).
- **pip-audit**: Failed to complete due to unsupported dependency `pywin32` (`artifacts/pip-audit.json` empty).
- **pytest**: Test run failed – missing dependencies `flask_mail` etc.

## Recommended Quick Wins
- Remove `.env` from repository and add to `.gitignore`.
- Rotate exposed SMTP credentials and any other secrets.
- Disable Flask debug mode and enforce proper environment settings.
- Add automated CodeQL and Semgrep scans via GitHub Actions.

## Strategic Improvements
- Implement dependency management with hash-locked requirements (e.g., `pip-tools`).
- Adopt secret management service (e.g., HashiCorp Vault, GitHub Secrets).
- Expand test coverage and ensure CI installs dependencies in a controlled environment.

## OWASP ASVS Mapping (Selected)
- **V2.1 – Authentication Secrets**: Fails due to committed credentials.
- **V14.4 – Configuration**: Fails because of debug mode and default secret key.

## Next Steps
1. Merge this report and associated workflows.
2. Rotate exposed credentials immediately.
3. Configure CodeQL and Semgrep tokens/secrets in repository settings.
4. Address medium/low findings and revisit dependency audit.

