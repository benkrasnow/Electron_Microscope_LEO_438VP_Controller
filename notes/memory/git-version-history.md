---
name: git-version-history
description: Complete_438VP_control - claude is a local git repo; commit after meaningful changes so versions can be restored
metadata:
  type: feedback
---

The project folder `Complete_438VP_control - claude` is a local git repository (created 2026-11-13, branch main, no remote). The user has never used git and said Claude is welcome to use it to restore previous versions.

**Why:** an over-broad automated edit once deleted most of `hardware/leo_control_box/tools/build_libs.py`; it had to be rewritten from memory.

**How to apply:** commit after each meaningful change (with the session's Co-Authored-By line); never push (no remote, and pushing is outward-facing). Local identity is set to the user's name/email. `.gitignore` excludes `scope_captures/*.npz` (6.8 GB) and KiCad backups/locks; `core.autocrlf` is false. Before risky bulk edits, commit first. Related: [[project-folder-layout]].
