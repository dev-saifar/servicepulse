# Security Report

## Executive Summary
- **Languages / Frameworks:** Python (Flask) application.
- **Package Management:** pip with `requirements.txt`.
- Semgrep and dependency audits could not fully run due to network and platform limitations. Secret scanning was executed.

## Threat Model
- User-authenticated Flask web app; secrets and credentials loaded from environment.
- Stores data in SQLite via SQLAlchemy; Celery and Redis handle background jobs.
- Sends emails using SMTP via Flask-Mail.
- Exposes web routes and background tasks which rely on .env configuration.

## Key Findings

### Critical
1. **Hardcoded credentials committed** – The repository previously contained `.env` with SMTP credentials and a license file with high-entropy secrets. These files were removed and added to `.gitignore` to prevent future leaks.
2. **Debug mode enabled in production code** – Flask app is configured with `DEBUG` and `ENV` set to development which exposes stack traces and other sensitive information if deployed【F:app/__init__.py†L35-L37】.

### High
1. **Static secret key fallback** – Application uses a default `SECRET_KEY` if environment variable is absent, reducing session integrity and CSRF protection【F:config.py†L6-L7】.

### Medium
1. **Missing automated security scanning in CI** – No CodeQL or Semgrep workflows existed, reducing visibility into vulnerabilities.
2. **Dependency audit failures** – `pip-audit` could not resolve Windows-specific packages (`pywin32`), preventing a full vulnerability assessment.

### Low
1. **Logging of client IP without rate limiting** – Request logging in `after_request` may expose sensitive info if logs are compromised【F:app/__init__.py†L48-L55】.

## Recommendations

### Quick Wins
- Ensure deployment config disables Flask debug mode and sets `ENV` to `production`.
- Set a strong `SECRET_KEY` via environment variables and rotate credentials.
- Remove sensitive files from version control and store secrets in a secure vault.
- Merge the added CodeQL and Semgrep workflows to enable continuous scanning.

### Strategic Improvements
- Implement centralized secret management (e.g., HashiCorp Vault, AWS Secrets Manager).
- Enforce dependency scanning in CI; consider replacing Windows-only packages or marking them optional for cross-platform builds.
- Add authentication/authorization checks across modules to meet OWASP ASVS guidelines.

## Additional Notes
- Semgrep scanning failed due to proxy restrictions (see `artifacts/semgrep-error.log`).
- Dependency audit (`pip-audit`) failed to resolve `pywin32` (see `artifacts/pip-audit.json`).
- Further manual review is recommended for database models and Celery tasks once dependency issues are resolved.
