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

## Floating — no version is pinned here

The only build arg is **`SONARQUBE_VERSION`** (default `community`). CI overrides
it with the newest **plugin-compatible** `…-community` tag via the
`resolve-versions` job, so the published image always tracks the freshest working
release.

The plugin is **not** a build arg: the Dockerfile reads the base image's
`$SONAR_VERSION` at build time, derives the matching plugin tag
(`<MAJOR>.<MINOR>.0`), downloads it under a version-less filename, and the
`-javaagent` `ENV` references that fixed name. Nothing to bump by hand — see
[`docs/branch-analysis.md`](../../docs/branch-analysis.md) and
[`docs/upgrade.md`](../../docs/upgrade.md).

## Local build & test

```bash
# A bare build floats on `community`; pass a plugin-compatible tag to be safe
# (mirrors what CI resolves), since `community` can run ahead of the plugin:
docker build \
  --build-arg SONARQUBE_VERSION=26.5.0.122743-community \
  -t sonarqube-bauer:test ./src/sonarqube

docker run --rm --entrypoint sh sonarqube-bauer:test \
  -c 'ls -l /opt/sonarqube/extensions/plugins/ && echo "$SONAR_WEB_JAVAADDITIONALOPTS"'
```

## License

The wrapper repository is MIT. The contained SonarQube Community Build and the
Community Branch Plugin are both LGPL-3.0.
