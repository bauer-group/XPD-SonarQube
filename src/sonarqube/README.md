# SonarQube Community Build — BAUER GROUP Edition

Thin wrapper around the upstream [`sonarqube`](https://hub.docker.com/_/sonarqube)
Community Build image with the
[Community Branch Plugin](https://github.com/mc1arke/sonarqube-community-branch-plugin)
baked into `/opt/sonarqube/extensions/plugins/`.

Published as `ghcr.io/bauer-group/XPD-SonarQube/sonarqube`.

## Why a wrapper image?

* **Reproducible branch analysis.** The branch plugin is version-locked to
  SonarQube. Baking it into the image layer means an image bump upgrades the
  plugin atomically — a stale `extensions/` volume can never shadow it.
* **Sovereign re-publish.** The stack keeps working from our own registry even
  if upstream tags move or disappear.

## Version pinning (bump as a pair)

| Build arg               | Default                     | Source                                             |
| ----------------------- | --------------------------- | -------------------------------------------------- |
| `SONARQUBE_VERSION`     | `26.5.0.122743-community`   | Docker Hub `library/sonarqube`                     |
| `BRANCH_PLUGIN_VERSION` | `26.5.0`                    | `mc1arke/sonarqube-community-branch-plugin` releases |
| `BRANCH_PLUGIN_SHA256`  | _(empty — skip check)_      | optional supply-chain verification of the JAR      |

The plugin `MAJOR.MINOR` **must equal** the SonarQube `MAJOR.MINOR`. Never pin
`SONARQUBE_VERSION` to the floating `community`/`latest` tag — it races ahead of
the plugin and a mismatched plugin stops SonarQube from starting. See
[`docs/upgrade.md`](../../docs/upgrade.md) and
[`docs/branch-analysis.md`](../../docs/branch-analysis.md).

## Local build & test

```bash
docker build \
  --build-arg SONARQUBE_VERSION=26.5.0.122743-community \
  --build-arg BRANCH_PLUGIN_VERSION=26.5.0 \
  -t sonarqube-bauer:test ./src/sonarqube

# The plugin must be present in the image:
docker run --rm sonarqube-bauer:test \
  ls -la /opt/sonarqube/extensions/plugins/
```

The `-javaagent` options that activate the plugin live in the compose files
(`SONAR_WEB_JAVAADDITIONALOPTS` / `SONAR_CE_JAVAADDITIONALOPTS`), kept visible
and coupled to the exact JAR filename — not hidden in this image.

## License

The wrapper repository is MIT. The contained SonarQube Community Build and the
Community Branch Plugin are both LGPL-3.0.
