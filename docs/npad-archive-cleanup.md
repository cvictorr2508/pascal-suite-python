# NPAD archive and cleanup for the inspected PaScal directories

Prepared on 20 November 2026 for the author's explicit archive/cleanup request.
This task is a scoped exception to the earlier no-new-home-files rule: maintenance
outputs go only beneath `/home/vrrcelestino/projects-archive`, and the four
inspected source directories may be removed only after their recovery checks.
The author executes these commands on NPAD; the maintainer does not access NPAD.

## Completed NPAD execution on 20 November 2026

The author supplied the successful preparation, recovery and cleanup output.
The maintainer reviewed that transcript; no independent remote NPAD session is
claimed. Ten synthetic tests passed on NPAD before the real-data operation.

Preserved private archive:

```text
/home/vrrcelestino/projects-archive/pascal-suite-python-20261120T193312Z-d4e0ebe7/pascal-suite-python-archive.tar.gz
```

- Archive SHA-256: `228a10f362d4876c404276ce1e30c50f2eee85d63e8f2f1160bc02a496fa5886`.
- Git bundle SHA-256: `1b6a44f6b77bf67eb2e47ffb40c78ef933780be8f56e851968eee1b589e7ae36`.
- Archived source file bytes: 945633522; compressed archive bytes: 611904502.
- Thirty symlinks verified; exact restoration and independent Git recovery passed.
- `cleanup_completed=true`; the final archive checksum passed again after cleanup.
- The two inspected worktrees were removed through Git; their empty parent,
  sync-backups, evidence and previous archive source directories were removed.
- The retained main clone was clean at `810317984e1b4050db05634ce7d30de64145fdba`,
  with only its own worktree registered, immediately after cleanup and before
  the subsequently authorized GitHub integration.

The tar, checksum, bundle, source manifests and validation/progress records stay
in that timestamped projects-archive directory. The first failed bundle attempt
and the maintenance tools/log directories were retained. Do not rerun cleanup
against the completed run or assume that the old source paths still exist.

The [closeout checkpoint](checkpoints/2026-11-20-closeout.md) identifies restart
constraints. Final integration commits and the later NPAD synchronization
receipt are recorded in [PR #33](https://github.com/cvictorr2508/pascal-suite-python/pull/33)
without changing source commits after the clone synchronization check.

## Findings and preservation policy

- The main clone is clean on `main` at
  `810317984e1b4050db05634ce7d30de64145fdba` after the author's fast-forward.
- The two linked worktrees have clean tracked/untracked status, but contain
  ignored solver logs and experimental results. Ignored does not mean expendable.
- The detached worktree is at `f41e88a3323ca00cb89ad31aab7abf0947e358cf`;
  the other is at `ed0fc307fb3e7b81e29c478517f3b6f4e937fade`.
  Both are reachable from named refs, and their Git common directory is the
  retained main clone's `.git` (about 8.1 MiB).
- The 12 KiB sync-backups directory contains two patches and a checksum record.
  Preserve all three files rather than assuming they are duplicates.
- Evidence is about 554 MiB; worktrees about 3.3 MiB; existing history about
  351 MiB. Preserve the old quarantine tar, its manifests and all other history.
- Existing evidence links use absolute original paths. Preserve the original
  link text in the archive and test a relocated copy independently.
- The reported quota is 44,141 MiB against a 100 GiB soft quota. The shared
  filesystem's free space is not the user's quota. Allow approximately 3 GiB
  of transient headroom for the archive and two recovery passes; actual size
  is checked, and no compression ratio is assumed.

No GitHub merge, scientific result regeneration, solver run, dependency install,
job cancellation or branch deletion is part of this operation. The existing
main clone and other projects-archive contents remain in place. Git removes
only the two inspected worktree registrations and directories.

## Archive layout

Each prepare run creates an exclusive private timestamped directory under
`projects-archive` and writes `pascal-suite-python-archive.tar.gz` containing:

```text
pascal-suite-python-archive/
  evidence/                 # complete original evidence, without dereferencing links
  worktrees/                # complete trees, including ignored logs/results/caches
  history/                  # complete previous pascal-suite-python-archive
  sync-backups/             # complete patch/checksum backup directory
  git-recovery.git/         # snapshot of the main clone's complete .git directory
  repository.bundle        # independently recoverable named Git history
  source-manifests.json     # per-file SHA-256, file type, modes and symlink targets
  worktrees-before.txt
```

The raw snapshot preserves link targets and file contents. Relocation is tested
only after exact extraction comparison, in a disposable copy. Original evidence
is never rewritten to make the test pass. File bytes, types, POSIX modes and link
text are compared; this is not an ACL/xattr migration tool or scientific re-audit.

## Prepare and validate

Use the already installed Python 3.13 environment. The script uses standard
library modules and Git; it performs no network Git fetch. Its production paths
are fixed. Place the script under projects-archive, outside the source roots.

```bash
python -B npad_archive_pascal.py prepare
```

Preparation checks main identity and cleanliness, exact worktree registrations
and commits, named-ref reachability, locks, jobs, process working directories,
source ownership and filesystem headroom. It creates an exclusive partial gzip
tar, fully extracts it, compares every recorded file/directory/link and rechecks
the sources. It then remaps links in the disposable copy and verifies that they
resolve inside that restored tree rather than to the live originals.

The Git bundle is cloned as an independent mirror and passes `git fsck`. Both
historical worktree commits and main are checked. Each restored worktree is then
made independent of the original common directory, using the recovered objects;
its index/HEAD and tracked/untracked status are checked. Ignored scientific data
were already verified by the full content manifest.

Only after these checks and a full gzip CRC read does the partial file become
the final tar.gz. Its SHA-256 and a validation receipt are written beside it.
The command prints `VALIDATED_RUN=/absolute/path`. Preparation removes no sources.

## Cleanup of only verified sources

```bash
python -B npad_archive_pascal.py cleanup --run /absolute/path/from/VALIDATED_RUN
```

Cleanup does not trust a success receipt alone: it checks the archive hash and
performs a fresh extraction, content comparison, link relocation and independent
Git recovery. It then repeats job/process, Git-state and source-content checks.
Any source change, missing file, external/broken link or mismatch stops cleanup.

The two worktrees are removed via `git worktree remove --force` only after
verification. Here `--force` permits removal of the fully preserved ignored logs
and results; tracked or non-ignored untracked changes are rejected beforehand.
Branches are retained. An unexpected nonempty parent directory is retained.

The sync-backups, evidence and previous history directories are each rechecked
immediately before recursive removal, restricted to the exact inspected roots.
The final tar checksum and main clone state are checked again. On success only
the script's own extraction-test directories are removed. Keep the tar, SHA-256,
bundle, source manifest, receipt and progress logs in projects-archive.

If a command fails, keep the saved run and logs. Do not replace the procedure
with `rm -rf`, reset, worktree prune or a forced branch operation. Partial cleanup
can have removed an already-preserved source before a later check fails; the
progress record identifies completed removals. Do not blindly rerun prepare
after such a partial cleanup.

## Recovery after cleanup

Extract into a new private directory and retain the original archive. The
archived Git pointer files refer to the original NPAD paths; they do not by
themselves make relocated worktrees independent. The same `restore_links` and
`recover_git` helpers used by both validation passes can reconstruct a relocated
working copy from the archive and bundle. They modify only that new extracted
copy, after verifying the raw snapshot. The original tar preserves historical
absolute link text, manifests and Git administration data for forensic recovery.

Preservation proves recovery of the current inspected bytes and Git state. It
does not retroactively certify completeness of an old scientific campaign or
repair an already missing external evidence chain. These private cluster
artifacts must not be uploaded into the public source repository.

## Validation

`tests/test_npad_archive_pascal.py` creates disposable synthetic repositories,
historical commits, detached/branched worktrees, ignored results and backups.
It tests recovery, corruption/source-change guards, worktree locks, tracked
changes, unsafe archive paths, confined deletion and relocatable links. The
Linux CI workflow runs the complete suite. Local Windows runs may skip Linux
deletion and symlink-privilege cases; these skips are not NPAD validation.

## Resource-limited service nodes and retry

Every Git invocation in this maintenance tool uses command-scoped `pack.threads=1`,
`index.threads=1`, `core.preloadIndex=false` and `gc.auto=0`. These settings bound
packing/index work and avoid automatic maintenance without editing the user's
or repository's persistent configuration. They apply to bundle creation and
independent clone/recovery operations as well as repository inspection.

A reported `unable to create thread` failure during `bundle create` occurs
before the tar is created or any source cleanup. It does not identify whether
memory, process limits or another service-node constraint caused thread creation
to fail. Preserve that failed run and its logs. Download the corrected pinned
script/test pair into a new maintenance tools directory and repeat `prepare`;
it chooses a fresh exclusive run directory. Use `cleanup` only with the newly
printed `VALIDATED_RUN`, never a failed or partial run. All existing recovery and
source-content checks remain mandatory. Do not compensate by running unbounded
packing, changing system limits, or moving work to a compute node without the
author's execution plan.

Official configuration reference:
https://git-scm.com/docs/git-config#Documentation/git-config.txt-packthreads
