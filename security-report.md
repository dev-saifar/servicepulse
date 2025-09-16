# Security Assessment Report

## Executive Summary

A security review of the ServicePulse Flask application identified exposed credentials, insecure defaults, and missing automated security scanning. Several tooling steps (Semgrep, pip-audit) could not complete due to network or dependency issues. Secret scanning with Gitleaks reported four potential leaks. Key risks include committed SMTP credentials and debugging enabled in production.

## Findings by Severity

| Severity | Finding |
|---|---|
| Critical | Plaintext SMTP credentials committed to the repository |
| High | Plaintext user passwords stored and emailed on account creation |
| High | Default Flask `SECRET_KEY` and debug mode enabled |
| Medium | Password reset emails contain temporary passwords in clear text |
| Medium | Security scanning tools (Semgrep, pip-audit) failed to execute |

## Detailed Findings

### 1. Plaintext SMTP Credentials (Critical)
- **Location:** `.env` lines 10-15
- **Risk:** Credentials in source control can be abused to send email or pivot into infrastructure. CWE-798 / OWASP A2.
- **Recommendation:** Remove `.env` from version control and load secrets via environment variables or a secret manager.

### 2. User Password Disclosure (High)
- **Location:** `app/modules/users.py` lines 35-36 and 114-115
- **Risk:** Application keeps a copy of the plaintext password to email new users. This exposes credentials to logs or attackers. CWE-256 / OWASP A3.
- **Recommendation:** Generate one-time reset links instead of emailing passwords. Remove plaintext handling.

### 3. Insecure Defaults (High)
- **Locations:**
  - `run.py` line 6 – debug mode enabled.
  - `config.py` line 6 – default `SECRET_KEY` is predictable.
- **Risk:** Attackers can trigger debug console or forge session cookies. CWE-732 / OWASP A5.
- **Recommendation:** Use `FLASK_ENV=production`, set `DEBUG=False`, and load a strong `SECRET_KEY` from a secret store.

### 4. Password Reset Sends Temporary Password (Medium)
- **Location:** `app/modules/auth.py` lines 71-100
- **Risk:** Temporary passwords sent via email can be intercepted. CWE-640 / OWASP A2.
- **Recommendation:** Use tokenized password reset links with short expiry instead of emailing passwords.

### 5. Tooling Gaps (Medium)
- **Observation:** Semgrep and pip-audit failed due to network restrictions and incompatible dependencies.
- **Risk:** Missing automated scanning allows vulnerabilities to go undetected.
- **Recommendation:** Enable CodeQL and Semgrep workflows (added in this PR) and fix pip-audit by refactoring Windows-only dependencies or running audits in compatible environments.

## Dependency & Secret Scan Summary
- **pip-audit:** Failed to run (`pywin32` has no Linux wheel).
- **Semgrep:** Could not download rules due to network restrictions.
- **Gitleaks:** Detected four potential secrets; review `artifacts/secrets.json` for details.

## Quick Wins
- Remove committed `.env` file and rotate exposed SMTP credentials.
- Disable debug mode and supply a strong `SECRET_KEY` via environment variables.
- Refactor user onboarding to avoid emailing passwords.

## Strategic Improvements
- Implement token-based password reset flow.
- Set up continuous security scanning via the provided CodeQL and Semgrep workflows.
- Integrate dependency auditing into CI once cross-platform issues are resolved.

## Next Steps & Remaining Tasks
- Rotate any potentially exposed credentials.
- Review Gitleaks findings for false positives and purge real secrets from history.
- Ensure `requirements.txt` is audited using a platform that supports Windows-specific packages or by removing unnecessary dependencies.
