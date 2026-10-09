# Branch & Pull-Request Analysis (Community Branch Plugin)

SonarQube **Community Build** analyses only the main branch natively. This stack
bundles the third-party
[Community Branch Plugin](https://github.com/mc1arke/sonarqube-community-branch-plugin)
to add branch and pull-request analysis.

## How it is wired (auto-resolved, no manual pin)

- The plugin JAR is **baked into the wrapper image** at
  `/opt/sonarqube/bundled-plugins/` (see `src/sonarqube/Dockerfile`), not
  installed via the Marketplace. The image's entrypoint installs it into
  `/opt/sonarqube/extensions/plugins/` on every start.
- The Dockerfile **resolves the plugin at build time** from the base image's own
  `$SONAR_VERSION` (plugin tag = `<MAJOR>.<MINOR>.0`) and keeps the release's
  file name, `sonarqube-community-branch-plugin-<version>.jar`. The `-javaagent`
  options are image-level `ENV` built from the same `BRANCH_PLUGIN_VERSION`
  build argument, so they never drift from the bundled JAR:

  ```text
  SONAR_WEB_JAVAADDITIONALOPTS=-javaagent:./extensions/plugins/sonarqube-community-branch-plugin-<version>.jar=web
  SONAR_CE_JAVAADDITIONALOPTS=-javaagent:./extensions/plugins/sonarqube-community-branch-plugin-<version>.jar=ce
  ```

- `/opt/sonarqube/extensions` is **deliberately not a named volume**. The
  upstream image still declares it a volume, and `docker compose up` hands the
  old container's anonymous volume to the new one on an upgrade, with the
  previous version of the plugin in it. The entrypoint therefore replaces every
  version of the bundled plugins there before SonarQube starts, so an upgrade
  always runs the plugin of the new image.

## Version locking — handled automatically ⚙

The plugin `MAJOR.MINOR` must equal the SonarQube `MAJOR.MINOR`; a mismatched
plugin refuses to load and SonarQube fails to start. The floating `community`
tag often runs ahead of the plugin, so this stack **floats on the plugin** and
matches SonarQube to it — there is nothing to pin by hand:

- The CI `resolve-versions` job takes the **latest branch-plugin release**, picks
  the newest SonarQube `<MAJOR.MINOR>.*-community` tag, builds with that pair and
  **commits it back into the Dockerfile `ARG` lines** — the Dockerfile stays the
  single, always-current source of truth.
- The base-image monitor watches the floating `sonarqube:community` tag and
  triggers a rebuild (re-resolve) on upstream drift.
- During the short window after a brand-new SonarQube release but before the
  matching plugin ships, the resolver stays on the previous working version.

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

If you ever want the plain Community Build without the plugin, override
`SONAR_WEB_JAVAADDITIONALOPTS` / `SONAR_CE_JAVAADDITIONALOPTS` to empty in the
compose `environment:` (the plugin JAR is then present but not activated), or
point `SONARQUBE_IMAGE` at the upstream `sonarqube:community` image directly.
