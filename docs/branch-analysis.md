# Branch & Pull-Request Analysis (Community Branch Plugin)

SonarQube **Community Build** analyses only the main branch natively. This stack
bundles the third-party
[Community Branch Plugin](https://github.com/mc1arke/sonarqube-community-branch-plugin)
to add branch and pull-request analysis.

## How it is wired

- The plugin JAR is **baked into the wrapper image** at
  `/opt/sonarqube/extensions/plugins/` (see `src/sonarqube/Dockerfile`), not
  installed via the Marketplace.
- The plugin runs as a `-javaagent` in **both** JVMs. The wrapper image sets
  these as image-level `ENV`, so they always match the bundled JAR:
  ```
  SONAR_WEB_JAVAADDITIONALOPTS=-javaagent:./extensions/plugins/sonarqube-community-branch-plugin-<ver>.jar=web
  SONAR_CE_JAVAADDITIONALOPTS=-javaagent:./extensions/plugins/sonarqube-community-branch-plugin-<ver>.jar=ce
  ```
- Because the plugin is in the image layer, `/opt/sonarqube/extensions` is
  **deliberately not a named volume** — a volume would shadow the plugin after an
  image upgrade and silently pin an old version.

## Version locking ⚠

The plugin `MAJOR.MINOR` **must equal** the SonarQube `MAJOR.MINOR`
(e.g. plugin `26.5.0` ↔ SonarQube `26.5.x`). A mismatched plugin refuses to load
and **SonarQube fails to start**.

- Pinned pair in this repo: SonarQube `26.5.0.122743-community` ↔ plugin `26.5.0`.
- **Never** point `SONARQUBE_BASE_VERSION` at the floating `community`/`latest`
  tag — it races ahead of the plugin's releases.
- Bump both together — see [upgrade.md](upgrade.md).

This plugin is **not supported by SonarSource**; using it is a deliberate
internal decision.

## Verifying it works

1. `Administration → Marketplace → Installed` should list the branch plugin.
2. Run two scans of the same project:
   ```bash
   sonar-scanner -Dsonar.projectKey=demo -Dsonar.host.url=https://${SONARQUBE_HOSTNAME} -Dsonar.token=$TOKEN
   sonar-scanner -Dsonar.projectKey=demo -Dsonar.branch.name=feature/x ...
   ```
   The `feature/x` branch should appear in the project's branch selector.
3. For PR decoration, configure the DevOps platform integration
   (GitHub/GitLab/etc.) under the project's **Administration → Pull Requests**.

## Disabling branch analysis

If you ever want the plain Community Build without the plugin, build the wrapper
with the plugin step removed (or override `SONAR_WEB_JAVAADDITIONALOPTS` /
`SONAR_CE_JAVAADDITIONALOPTS` to empty in the compose `environment:`), and you
may then pin `SONARQUBE_BASE_VERSION` to the floating `community` tag.
