# Reverse Proxy & Base URL

SonarQube listens on port `9000` (plain HTTP) inside the container. TLS is
terminated at the edge (Traefik / Coolify), which forwards to `9000`.

## Server base URL

Set the public URL so SonarQube generates correct links in notifications and
pull-request decoration:

- `.env`: `SONARQUBE_SERVER_BASE_URL=https://sonarqube.development.app.bauer-group.com`
- The compose files pass it through as `SONAR_CORE_SERVERBASEURL`
  (the `sonar.core.serverBaseURL` property).

You can also confirm/override it in the UI under **Administration → Configuration
→ General → Server base URL**.

## Forwarded headers

Behind a proxy, SonarQube must trust the `X-Forwarded-*` headers so it knows the
original scheme/host is HTTPS. Traefik sets `X-Forwarded-Proto`, `X-Forwarded-Host`
and `X-Forwarded-For` automatically when routing through a router — no extra
SonarQube config is required for the standard setup in this repo.

Symptoms of a misconfigured proxy:

- redirect loops or "CSRF" / "Unauthorized" right after login → the scheme seen
  by SonarQube is `http` while the browser uses `https`; verify TLS terminates at
  Traefik and the router has `tls=true`, and that `SONAR_CORE_SERVERBASEURL` is
  the HTTPS URL.
- avatar/logo or e-mail links point at `http://` or an internal host → set
  `SONARQUBE_SERVER_BASE_URL` correctly and restart.

## Traefik routing (this repo)

`docker-compose.traefik.yml` ships the labels:

- a shared `${STACK_NAME}-redirect` middleware (HTTP → HTTPS, permanent)
- router `${STACK_NAME}-app-http` on `web` → applies the redirect
- router `${STACK_NAME}-app` on `web-secure` → `tls.certresolver=letsencrypt`,
  forwarding to `loadBalancer.server.port=9000`

No buffering tweaks are needed for normal scanner uploads; if you push very large
analysis reports through Traefik you may raise client/response timeouts on the
entrypoint, but the defaults are fine for typical projects.
