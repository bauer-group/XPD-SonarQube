# Installation

Three deployment paths share one service layer (SonarQube + PostgreSQL + a
privileged kernel-init sidecar + an optional backup sidecar). Pick the variant
that matches your environment.

## 0. Common prerequisites

- Docker Engine + Compose v2
- A generated `.env`:
  ```bash
  python scripts/generate-env.py     # fills POSTGRES_PASSWORD
  ```
  Then review `SONARQUBE_HOSTNAME`, JVM heap presets, and (optionally) the
  `SMTP_*` and `SONARQUBE_BACKUP_*` sections.
- **Kernel:** SonarQube embeds Elasticsearch and requires
  `vm.max_map_count >= 524288` and high file/process limits. The privileged
  `sonarqube-init` service applies the sysctls automatically on every start, and
  the `sonarqube` service sets the ulimits (`nofile 131072`, `nproc 8192`). No
  manual host step is needed.

  If your platform forbids privileged containers, remove the `sonarqube-init`
  service and set the sysctl on the host instead:
  ```bash
  echo 'vm.max_map_count=524288' | sudo tee /etc/sysctl.d/99-sonarqube.conf
  echo 'fs.file-max=131072'      | sudo tee -a /etc/sysctl.d/99-sonarqube.conf
  sudo sysctl --system
  ```

## A. Local development

Builds the wrapper image (SonarQube + branch plugin) locally and publishes the
UI on `http://localhost:9000`.

```bash
docker compose -f docker-compose.development.yml up -d --build
docker compose -f docker-compose.development.yml logs -f sonarqube   # wait for "SonarQube is operational"
```

## B. Production — Traefik

Pulls the published wrapper image and routes via your existing Traefik instance.

1. DNS: point `SONARQUBE_HOSTNAME` (an A/AAAA record) at the Traefik host.
2. Traefik must run on the external `${PROXY_NETWORK}` (default `EDGEPROXY`)
   network with `web`/`web-secure` entrypoints and a `letsencrypt` cert resolver.
3. Start:
   ```bash
   docker compose -f docker-compose.traefik.yml up -d
   ```
4. Browse to `https://${SONARQUBE_HOSTNAME}` and log in as `admin` / `admin`.

## C. Production — Coolify

1. Create a new resource from `docker-compose.coolify.yml`.
2. In the Coolify UI set the `sonarqube` service domain to `${SONARQUBE_HOSTNAME}`
   and the port to `9000`. Coolify generates the router and TLS.
3. Set `POSTGRES_PASSWORD`, `SONARQUBE_HOSTNAME` (and any `SMTP_*` /
   `SONARQUBE_BACKUP_*`) as environment variables in the dashboard, then deploy.

## First login & e-mail

- Default credentials: `admin` / `admin` — you must change the password on first
  login. Then create a dedicated technical user / token for CI scanners.
- **E-mail notifications** (quality-gate failures etc.) are configured in the
  SonarQube web UI under **Administration → Configuration → General → Email** —
  they are stored in the database, not in `.env`. The `SMTP_*` variables in
  `.env` feed the **backup sidecar** alerting, not SonarQube itself.
