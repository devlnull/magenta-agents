# Release a new version

1. Optional: copy `standards/organization.example.md` to `standards/organization.md` and write your organization standards.
2. Increase `release` in `magenta.yaml`.
3. Add the changes to [`CHANGELOG.md`](../CHANGELOG.md). Optional: write longer release notes in `docs/releases/v<version>.md`.
4. Run `python3 magenta.py build`. It also updates the committed plugin (`plugins/magenta/`, `.claude-plugin/marketplace.json`).
5. Run `python3 magenta.py check` and `python3 -m unittest discover -s tests`. Commit and push.
6. Create and push the tag: `git tag v<version> && git push origin v<version>`.

The tag starts the `release` workflow. It runs the full CI on macOS, Linux, and Windows, checks that the tag agrees with `magenta.yaml`, builds the assets with `python3 magenta.py package`, and publishes the GitHub release:

| Asset | Content |
|---|---|
| `magenta-agents-<version>.zip` | The source and the built files for all tools. Installs without network: unzip, then `python3 magenta.py install`. |
| `magenta-plugin-<version>.zip` | The Claude Code plugin marketplace. |
| `SHA256SUMS` | The checksums. |

The release text comes from `docs/releases/v<version>.md`. Without that file, GitHub writes notes from the commits.

To publish a tag that exists already, run the `release` workflow by hand (Actions, release, Run workflow) and give the tag.
