# Users & Security

How identity, credentials and the runtime are managed in this stack.

## Identity — two separate layers

### 1. Database (infrastructure)

* A dedicated PostgreSQL user **`sonar`** with a generated **`POSTGRES_PASSWORD`**
  (32 hex chars from `scripts/generate-env.py`).
* PostgreSQL is reachable only on the internal `local` network — **no public
  port** in the `traefik` / `coolify` variants (the `development` variant
  publishes 5432 locally for debugging only).
* SonarQube connects via JDBC with these credentials.

### 2. SonarQube application (logins)

* **SonarQube keeps its own user store in the PostgreSQL database.**
* The first administrator is bootstrapped as **`admin` / `admin`** → SonarQube
  **forces a password change on first login**.
* Additional users are managed under **Administration → Security → Users**, or
  provisioned via SSO (see [authentication.md](authentication.md)).
* CI scanners authenticate with **user tokens** (My Account → Security →
  Tokens), never with username/password.

## First-login hardening checklist

1. Log in as `admin` / `admin` and set a strong admin password (forced).
2. Create a dedicated **technical user + token** for CI/scanners; don't reuse
   the admin account.
3. Decide on authentication: local accounts vs. developer SSO
   ([GitHub auth or Zitadel OIDC](authentication.md)). With SSO, disable
   self-registration so only known identities get in.
4. Keep **Force user authentication** enabled (default) — no anonymous access.

## Secrets

* `.env` is **git-ignored** and hardened to **`chmod 600`** on POSIX; the repo
  only ships `CHANGE_ME_*` placeholders — **no secrets in git**.
* Only `POSTGRES_PASSWORD` is auto-generated. SMTP and backup-target S3
  credentials are operator-supplied and empty by default.
* `.gitignore` excludes `.env` / `.env.*` (except `.env.example`).

## Network & runtime

* Only SonarQube's port `9000` is exposed, via Traefik with HTTPS
  (Let's Encrypt). The database and the init sidecar are never public.
* Containers run **non-root** (uid 1000). The only privileged container is the
  one-shot `sonarqube-init`, which exists solely to set the `vm.max_map_count`
  / `fs.file-max` sysctls the embedded Elasticsearch requires.
* `SONAR_CORE_SERVERBASEURL` is set so notification/PR links use the real
  HTTPS host; Traefik forwards the `X-Forwarded-*` headers.
* Images carry SBOMs and full OCI provenance labels; versions are pinned and
  reproducible.

See [authentication.md](authentication.md) for wiring developer SSO (GitHub / Zitadel).
