# Solar of Things vendor provenance

This directory is a source snapshot derived from the public
[`Conexo-Casa/solar-of-things-ha`](https://github.com/Conexo-Casa/solar-of-things-ha)
Home Assistant integration, which is distributed under the MIT License included
in [LICENSE](LICENSE).

The original local snapshot identified itself as
`HomeAssistant-SolarOfThings/2.3.0` in its request user agent. It predates the
current upstream `v2.7.1` release and is intentionally retained because it is
the verified reader used by this application. It includes a project-local
adaptation that removes the upstream user-ID debug log. It is not an installed
PyPI dependency and must not be replaced with an unpinned package at build time.

The reproducible application snapshot consists of exactly these files:

| File | SHA-256 |
|---|---|
| `__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `api.py` | `34011224c25f01123b2b2fd1b939bf69a023a561b8492c748398bcbfda8cb0af` |
| `const.py` | `f8ddce94cc0dfbb7b746fdf5233f5926475ac8f87aa0164a3c418fc60f4054f9` |

The vendor code contains Siseli portal client-signing material already present
in the public upstream project. It is not this installation's BEVE credential,
Tuya credential, setup code, JWT key, database password, or runtime master key.
Those installation secrets remain external to Git and container images.

Before changing this snapshot, review the upstream MIT license, compare the
candidate revision, update this provenance and hashes, run the read-only BEVE
tests, and confirm no inverter write path is exposed by this application.
