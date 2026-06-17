# SonarQube — Self-Hosted Stack (BAUER GROUP)

Professional, self-hosted [SonarQube Community Build](https://www.sonarsource.com/products/sonarqube/)
for internal code quality & static analysis, with **branch / pull-request
analysis** enabled via the Community Branch Plugin. Production target:
`https://sonarqube.development.app.bauer-group.com`.

Built to the same conventions as the other BAUER GROUP container stacks:
Traefik/EDGEPROXY edge, named volumes, `${STACK_NAME}` prefixes, GHCR wrapper
images, `semantic-release`, Dependabot and daily base-image monitoring.

## Highlights

| | |
| --- | --- |
| 🧪 **Code quality & SAST** | SonarQube Community Build, latest pinned release |
| 🌿 **Branch & PR analysis** | Community Branch Plugin baked into the wrapper image |
| 🐘 **PostgreSQL** | Tuned `postgres:16-alpine` (no pgvector needed) |
| 🔐 **HTTPS** | Traefik + Let's Encrypt on a dedicated subdomain |
| ⚙️ **Kernel-ready** | Privileged init sidecar sets `vm.max_map_count` automatically |
| 💾 **Backups** | Optional scheduled `pg_dump` sidecar (S3 off-site + alerting) |
| 🚀 **CI/CD** | semantic-release, multi-image build, Dependabot, base-image monitor |

## Architecture

```text
  Browsers / Scanners / CI runners
            │
            ▼  HTTPS (Let's Encrypt)
       ┌─────────┐
       │ Traefik │  ── proxy network (external: EDGEPROXY)
       └────┬────┘
            │
   ┌────────▼─────────────────────────────────┐
   │  sonarqube  ──►  db (PostgreSQL 16)        │  ── local network
   │     ▲                                       │
   │     └── sonarqube-init (sets vm.max_map_count, one-shot, privileged)
   │  sonarqube-backup (optional, profile: backup) ──► db
   └─────────────────────────────────────────────┘
```

## Quick start

```bash
# 1. Generate .env with a random POSTGRES_PASSWORD
python scripts/generate-env.py
#    then review SONARQUBE_HOSTNAME and (optionally) SMTP_* / backup settings

# 2a. Local development (builds the wrapper image, publishes on :9000)
docker compose -f docker-compose.development.yml up -d --build

# 2b. Production with Traefik (pulls the published wrapper image)
docker compose -f docker-compose.traefik.yml up -d

# 3. First login: admin / admin → you are forced to set a new password
#    Web UI: http://localhost:9000  (dev)  /  https://${SONARQUBE_HOSTNAME}  (prod)
```

> **Host prerequisite recap:** SonarQube embeds Elasticsearch and needs
> `vm.max_map_count >= 524288`. The privileged `sonarqube-init` service applies
> it on every start, so no manual host step is required. If you prefer to set it
> on the host instead, see [docs/installation.md](docs/installation.md).

## Repository layout

```text
.
├── docker-compose.development.yml   # local: direct ports (pulls images)
├── docker-compose.traefik.yml       # production: EDGEPROXY + Let's Encrypt
├── docker-compose.coolify.yml       # production: Coolify dashboard
├── .env.example                     # full configuration contract
├── scripts/generate-env.py          # secret generator (stdlib, cross-platform)
├── src/
│   ├── sonarqube/                   # wrapper image: Community Build + branch plugin
│   └── sonarqube-backup/            # pg_dump backup sidecar (Python, tested)
├── docs/                            # installation, reverse-proxy, branch-analysis, backup, upgrade
└── .github/                         # CI/CD: release, docker build, dependabot, monitors
```

## Editions & versions (all floating — no manual pinning)

Every tag floats so the stack auto-updates to current, patched software. CI
rebuilds the wrapper images and the daily base-image monitor catches digest
drift — there are no version numbers to maintain by hand.

| Component      | Tag (floating)        | Updates via                     |
| -------------- | --------------------- | ------------------------------- |
| SonarQube base | `sonarqube:community` | CI resolver (plugin-compatible) |
| Branch plugin  | derived from base     | Dockerfile (no pin)             |
| PostgreSQL     | `postgres:16-alpine`  | patch-floating                  |
| Backup base    | `python:3.14-alpine`  | patch-floating + Dependabot     |
| Init sidecar   | `busybox:stable`      | floating                        |
| Wrapper images | `sonarqube:latest`    | CI + base-image monitor         |

The Community Build only analyses the main branch natively — the bundled
**Community Branch Plugin** adds branch & PR analysis. It is a third-party
plugin (not supported by SonarSource) and is version-locked to SonarQube;
the build resolves the matching plugin automatically. See
[docs/branch-analysis.md](docs/branch-analysis.md) and
[docs/upgrade.md](docs/upgrade.md).

## Operations

```bash
# Health
curl -s http://localhost:9000/api/system/status        # {"status":"UP",...}
docker compose -f docker-compose.traefik.yml logs -f sonarqube

# Backups (profile: backup)
docker compose -f docker-compose.traefik.yml --profile backup run --rm sonarqube-backup --now
docker compose -f docker-compose.traefik.yml --profile backup run --rm sonarqube-backup list
```

See [docs/backup.md](docs/backup.md) for the full backup/restore playbook.

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| SonarQube container restarts, ES log: `max virtual memory areas … too low` | `vm.max_map_count` not applied — ensure `sonarqube-init` ran (it needs `privileged`); see docs/installation.md |
| Branch / PR tab missing | branch plugin not active — version mismatch with SonarQube; see docs/branch-analysis.md |
| Links in e-mails / PRs use the wrong host | set `SONARQUBE_SERVER_BASE_URL` (→ `SONAR_CORE_SERVERBASEURL`); see docs/reverse-proxy.md |
| Login loop / CSRF behind proxy | Traefik must forward `X-Forwarded-*`; see docs/reverse-proxy.md |

## Documentation

- [docs/installation.md](docs/installation.md) — development / traefik / coolify
- [docs/reverse-proxy.md](docs/reverse-proxy.md) — base URL, forwarded headers, TLS
- [docs/branch-analysis.md](docs/branch-analysis.md) — Community Branch Plugin
- [docs/backup.md](docs/backup.md) — backup & restore
- [docs/upgrade.md](docs/upgrade.md) — version upgrades & plugin compatibility

## License

This repository is MIT. SonarQube Community Build and the Community Branch
Plugin are LGPL-3.0.
