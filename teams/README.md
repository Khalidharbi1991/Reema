# Teams

Each REEMA section keeps its own local files here. Code stays shared in `src/`.
Everything below this README is ignored by Git (`/teams/*/` in `.gitignore`).

| Folder | Section | Holds |
| --- | --- | --- |
| `coordination/data/` | Coordination (Ahmad, executive assistant) | Work and personal task and memory stores, used only through the `task` and `memory` commands |
| `coordination/snafi-backups/` | Coordination (Snafi) | Khalid's daily Snafi backups (`snafi-backup-YYYYMMDD-HHMM.json.gz`, newest 30 days), written by the Snafi worker. Personal data: no Claude Code session or agent may read it (deny rules and `dev_guard.py`). Written by the `worker` Windows user; restore as that user with `C:\SnafiWorker\snafi.cmd restore` (see `src/snafi_worker/README.md`) |
| `documentation/input/references/` | Documentation (Abdullah) | Reference material and its manifest |
| `documentation/input/diagrams/` | Documentation | Process diagram sources |
| `documentation/output/` | Documentation | Runs, Claude Code requests, published SOPs and archive |
| `home-design/New Home/` | Home Design (Agent 9) | The New Home project, its own local git repo with its own `input/` and `output/` |
| `home-design/legacy-output/` | Home Design | Earlier concept output from before the New Home project |
| `development/projects/<name>/` | Development (Agent 11) | One local git repo per project |

Logs stay shared in `logs/`.
