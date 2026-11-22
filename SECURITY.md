# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in **PayGuard AI**, please **do not** open a public GitHub issue or pull request exposing exploit details.

Instead, report it privately to **shatwik7@gmail.com** with:
- A clear description of the vulnerability and affected endpoint/file.
- Steps to reproduce or a minimal proof of concept.
- Potential impact assessment.

You will receive an acknowledgment within **48 hours** and a remediation plan as soon as the issue is verified.

## Security Practices Enforced
- Secrets and credentials are loaded exclusively from environment variables (never committed to Git).
- Strict CORS origin allowlisting without wildcard credential reflection.
- HTTP security response headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, and `HSTS` in production).
- Input validation, rate limiting, and fail-closed production configuration checks.
