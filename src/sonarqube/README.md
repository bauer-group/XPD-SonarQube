# SonarQube Community Build — BAUER GROUP Edition

Thin wrapper around the upstream [`sonarqube`](https://hub.docker.com/_/sonarqube)
Community Build image with the
[Community Branch Plugin](https://github.com/mc1arke/sonarqube-community-branch-plugin)
baked into `/opt/sonarqube/extensions/plugins/`.

Published as `ghcr.io/bauer-group/XPD-SonarQube/sonarqube`.

## Why a wrapper image?

* **Reproducible branch analysis.** The branch plugin is version-locked to
  SonarQube. Baking it into the image layer means a rebuild upgrades the plugin
  atomically — a stale `extensions/` volume can never shadow it.
* **Sovereign re-publish.** The stack keeps working from our own registry even
  if upstream tags move.

## Versions: pinned in the Dockerfile, auto-maintained

Two explicit build args are the **single source of truth** — and they stay
current automatically, so the Dockerfile always shows what's actually built:

* **`SONARQUBE_VERSION`** (e.g. `26.5.0.122743-community`) — the base image tag.
* **`BRANCH_PLUGIN_VERSION`** (e.g. `26.5.0`) — the branch-plugin release; its
  `MAJOR.MINOR` must equal SonarQube's.
* **`BRANCH_PLUGIN_SHA256`** (optional, empty by default) — supply-chain check of the JAR.

The CI `resolve-versions` job finds the newest **plugin-compatible** pair
(latest branch-plugin release → newest matching `…-community` SonarQube tag),
builds with it, **and commits the pair back into these `ARG` lines** (GITHUB_TOKEN
pushes don't re-trigger CI, so it never loops). The daily base-image monitor
re-runs it on `sonarqube:community` drift. Net effect: published image == this
Dockerfile, always current, fully reproducible — see
[`docs/upgrade.md`](../../docs/upgrade.md).

The plugin JAR is named with its version (`sonarqube-community-branch-plugin-<ver>.jar`)
and the `-javaagent` `ENV` references that exact name.

## Local build & test

```bash
# Builds the pinned pair from the Dockerfile (reproducible, offline):
docker build -t sonarqube-bauer:test ./src/sonarqube

docker run --rm --entrypoint sh sonarqube-bauer:test \
  -c 'ls -l /opt/sonarqube/extensions/plugins/ && echo "$SONAR_WEB_JAVAADDITIONALOPTS"'
```

## License

The wrapper repository is MIT. The contained SonarQube Community Build and the
Community Branch Plugin are both LGPL-3.0.
