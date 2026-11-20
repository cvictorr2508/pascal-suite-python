#!/usr/bin/env python3
"""Archive, independently recover, then conditionally remove inspected NPAD data.

Python 3.13, standard library and Git only. No solver, SSH, fetch or GitHub merge.
Production paths are deliberately fixed to the user's November 20 request.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import tarfile
import uuid

BASE = Path('/home/vrrcelestino')
PREFIX = 'pascal-suite-python-archive'
MAIN = '810317984e1b4050db05634ce7d30de64145fdba'
WORKTREES = {
    'gurobi-hard-default-8h-f41e88a': 'f41e88a3323ca00cb89ad31aab7abf0947e358cf',
    'gurobi-hard-minimize-2681a09': 'ed0fc307fb3e7b81e29c478517f3b6f4e937fade',
}
ROOTS = {
    'evidence': 'pascal-suite-python-evidence',
    'worktrees': 'pascal-suite-python-worktrees',
    'history': 'pascal-suite-python-archive',
    'sync-backups': 'pascal-suite-python-sync-backups',
    'git-recovery.git': 'pascal-suite-python/.git',
}
GIT_RESOURCE_OPTIONS = (
    '-c', 'pack.threads=1',
    '-c', 'index.threads=1',
    '-c', 'core.preloadIndex=false',
    '-c', 'gc.auto=0',
)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def command(args, cwd=None):
    args = [str(value) for value in args]
    if args[0] == 'git':
        # Service nodes may expose many CPUs but forbid creating worker threads.
        # CLI settings also reach clone/pack children without editing Git config.
        args = [args[0], *GIT_RESOURCE_OPTIONS, *args[1:]]
    env = os.environ.copy()
    for name in list(env):
        if name.startswith('GIT_'):
            del env[name]
    env['GIT_OPTIONAL_LOCKS'] = '0'
    result = subprocess.run(args, cwd=cwd, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding='utf-8', errors='replace')
    require(result.returncode == 0,
            f'Command failed: {args!r}\n{result.stdout}\n{result.stderr}')
    return result.stdout.strip()


def git(root, *args):
    return command(['git', '-C', root, *args])


def snapshot(root):
    """Never follow symlinks; include ignored files, directories and link text."""
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), f'Unsafe root: {root}')
    records = {}

    def visit(path, relative):
        info = path.lstat()
        row = {'mode': stat.S_IMODE(info.st_mode)}
        if stat.S_ISLNK(info.st_mode):
            row.update(type='link', target=os.readlink(path))
        elif stat.S_ISREG(info.st_mode):
            row.update(type='file', bytes=info.st_size, sha256=digest(path))
        elif stat.S_ISDIR(info.st_mode):
            row.update(type='dir')
        else:
            raise RuntimeError(f'Special file is not supported: {path}')
        records[relative] = row
        if row['type'] == 'dir':
            for child in sorted(path.iterdir()):
                visit(child, f'{relative}/{child.name}' if relative else child.name)

    visit(root, '')
    return records


def ensure_equal(actual, expected, label):
    require(actual == expected, f'Content/mode/link mismatch: {label}; no cleanup allowed')


def jobs_and_processes(base):
    require(shutil.which('squeue') is not None, 'squeue is required for the safety check')
    jobs = command(['squeue', '--noheader', '--user', str(os.getuid()), '--format=%i'])
    require(not jobs, f'User has active/pending jobs; stop first: {jobs}')
    protected = [str(base / name) for key, name in ROOTS.items() if key != 'git-recovery.git']
    if Path('/proc').is_dir():
        for proc in Path('/proc').iterdir():
            if not proc.name.isdigit():
                continue
            try:
                if proc.stat().st_uid != os.getuid():
                    continue
                cwd = os.readlink(proc / 'cwd')
            except (OSError, PermissionError):
                continue
            require(not any(cwd == p or cwd.startswith(p + '/') for p in protected),
                    f'Process {proc.name} has a cwd in a source directory: {cwd}')


def inspect_repo(base, main=None, worktrees=None):
    main = MAIN if main is None else main
    worktrees = WORKTREES if worktrees is None else worktrees
    repo = base / 'pascal-suite-python'
    require(git(repo, 'remote', 'get-url', 'origin') in {
        'git@github.com:cvictorr2508/pascal-suite-python.git',
        'https://github.com/cvictorr2508/pascal-suite-python.git',
        'https://github.com/cvictorr2508/pascal-suite-python',
    }, 'Unexpected origin identity')
    require(git(repo, 'symbolic-ref', '--short', 'HEAD') == 'main', 'Main clone changed branch')
    require(git(repo, 'rev-parse', 'HEAD') == main, 'Main HEAD differs from inspected commit')
    require(not git(repo, 'status', '--porcelain=v1', '--untracked-files=all'), 'Main clone is dirty')
    registrations = git(repo, 'worktree', 'list', '--porcelain')
    observed = {line[9:] for line in registrations.splitlines() if line.startswith('worktree ')}
    expected = {str(repo), *(str(base / ROOTS['worktrees'] / name) for name in worktrees)}
    # Git for Windows prints slashes, used only by the synthetic local tests.
    normalize = lambda p: p.replace('\\', '/').removeprefix('//?/')
    require({normalize(p) for p in observed} ==
            {normalize(p) for p in expected}, 'Unexpected worktree registrations')
    for name, sha in worktrees.items():
        wt = base / ROOTS['worktrees'] / name
        require(git(wt, 'rev-parse', 'HEAD') == sha, f'Worktree HEAD changed: {name}')
        require(not git(wt, 'status', '--porcelain=v1', '--untracked-files=all'),
                f'Tracked/untracked changes require review: {name}')
        require(git(repo, 'for-each-ref', '--contains', sha, '--format=%(refname)'),
                f'Commit is not protected by a named ref: {sha}')
        gitdir = Path(git(wt, 'rev-parse', '--absolute-git-dir'))
        require(not (gitdir / 'locked').exists(), f'Worktree is locked: {name}')
        require(not (wt / '.gitmodules').exists(), 'Submodules require a separate recovery procedure')
    return registrations


def extract_checked(archive, destination):
    """Validate all member paths before allowing preserved absolute symlinks."""
    require(not destination.exists(), 'Restoration destination already exists')
    with tarfile.open(archive, 'r:gz') as tar:
        members = tar.getmembers()
        names = [m.name.rstrip('/') for m in members]
        require(len(names) == len(set(names)), 'Duplicate archive members')
        links = {m.name.rstrip('/') for m in members if m.issym()}
        for member in members:
            path = PurePosixPath(member.name)
            require(not path.is_absolute() and '..' not in path.parts and
                    path.parts and path.parts[0] == PREFIX, 'Unsafe archive member')
            require(not any(str(p) in links for p in path.parents),
                    'Archive member lies beneath a symlink')
            require(member.isfile() or member.isdir() or member.issym() or member.islnk(),
                    'Special archive member')
            if member.islnk():
                target = PurePosixPath(member.linkname)
                require(not target.is_absolute() and '..' not in target.parts and
                        target.parts and target.parts[0] == PREFIX and str(target) in names,
                        'Unsafe hard-link target')
        destination.mkdir()
        if os.name == 'nt':
            # Local Windows fixtures use extended paths; tarfile's final
            # directory attribute pass otherwise retains invalid '/' separators.
            for member in members:
                member.name = member.name.replace('/', os.sep)
                if member.islnk():
                    member.linkname = member.linkname.replace('/', os.sep)
        tar.extractall(destination, members=members, filter='fully_trusted')
    return destination / PREFIX


def restore_links(tree, base, manifests):
    """Rewrite only the disposable restoration copy after byte-exact checking."""
    count = 0
    for label, records in manifests.items():
        source = base / ROOTS[label]
        for relative, row in records.items():
            if row['type'] != 'link':
                continue
            original = Path(os.path.abspath(os.path.join(source / relative, '..', row['target'])))
            if os.path.isabs(row['target']):
                original = Path(os.path.normpath(row['target']))
            mapped = None
            for candidate, source_name in ROOTS.items():
                source_root = base / source_name
                if original.is_relative_to(source_root):
                    mapped = tree / candidate / original.relative_to(source_root)
                    break
            require(mapped is not None, f'External symlink target requires review: {original}')
            link = tree / label / relative
            link.unlink()
            link.symlink_to(os.path.relpath(mapped, link.parent), target_is_directory=mapped.is_dir())
            count += 1
    for label, records in manifests.items():
        for relative, row in records.items():
            if row['type'] == 'link':
                link = tree / label / relative
                resolved = link.resolve(strict=True)
                require(resolved.is_relative_to(tree.resolve()), 'Restored link escapes test tree')
    return count


def recover_git(tree, worktrees=None, main=None):
    main = MAIN if main is None else main
    worktrees = WORKTREES if worktrees is None else worktrees
    mirror = tree.parent / 'recovery-mirror.git'
    command(['git', 'clone', '--mirror', tree / 'repository.bundle', mirror])
    git(mirror, 'fsck', '--full', '--no-reflogs')
    for sha in [main, *worktrees.values()]:
        git(mirror, 'cat-file', '-e', sha + '^{commit}')
    for name, sha in worktrees.items():
        wt = tree / 'worktrees' / name
        pointer = wt / '.git'
        require(pointer.is_file() and not pointer.is_symlink(), 'Unexpected restored .git pointer')
        pointer.unlink()  # Disposable copy only; original pointer remains inside the tar.
        git(wt, 'init', '--quiet')
        require(not (mirror / 'objects/info/alternates').exists(), 'Recovery mirror uses external objects')
        shutil.copytree(mirror / 'objects', wt / '.git/objects', dirs_exist_ok=True)
        git(wt, 'update-ref', '--no-deref', 'HEAD', sha)
        git(wt, 'read-tree', sha)
        git(wt, 'fsck', '--full', '--no-reflogs')
        require(not git(wt, 'status', '--porcelain=v1', '--untracked-files=all'),
                f'Independent worktree recovery is dirty: {name}')


def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def prepare(base):
    jobs_and_processes(base)
    registrations = inspect_repo(base)
    for source in ROOTS.values():
        path = base / source
        require(path.is_dir() and not path.is_symlink(), f'Invalid source root: {path}')
        require(path.stat().st_uid == os.getuid(), f'Source root is not owned by user: {path}')
    destination = base / 'projects-archive'
    require(destination.is_dir() and not destination.is_symlink(), 'Invalid projects-archive directory')
    name = 'pascal-suite-python-' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    run = destination / name
    run.mkdir(mode=0o700)
    bundle = run / 'repository.bundle'
    print(f'RUN={run}', flush=True)
    git(base / 'pascal-suite-python', 'bundle', 'create', bundle, '--all')
    git(base / 'pascal-suite-python', 'bundle', 'verify', bundle)
    manifests = {label: snapshot(base / source) for label, source in ROOTS.items()}
    logical_bytes = sum(r.get('bytes', 0) for records in manifests.values() for r in records.values())
    require(shutil.disk_usage(destination).free > 3 * logical_bytes,
            'Insufficient filesystem free space for compression and test restoration')
    save(run / 'source-manifests.json', manifests)
    (run / 'worktrees-before.txt').write_text(registrations + '\n', encoding='utf-8')
    archive = run / (PREFIX + '.tar.gz')
    partial = run / (archive.name + '.partial')
    with tarfile.open(partial, 'x:gz', format=tarfile.PAX_FORMAT, dereference=False,
                      compresslevel=6) as tar:
        for label, source in ROOTS.items():
            tar.add(base / source, arcname=PREFIX + '/' + label)
        tar.add(bundle, arcname=PREFIX + '/repository.bundle')
        tar.add(run / 'source-manifests.json', arcname=PREFIX + '/source-manifests.json')
        tar.add(run / 'worktrees-before.txt', arcname=PREFIX + '/worktrees-before.txt')
    tree = extract_checked(partial, run / 'restore-test')
    for label, expected in manifests.items():
        ensure_equal(snapshot(tree / label), expected, 'extracted ' + label)
        ensure_equal(snapshot(base / ROOTS[label]), expected, 'source ' + label)
    links = restore_links(tree, base, manifests)
    recover_git(tree)
    # Force gzip trailer/CRC validation, including any trailing stream data.
    import gzip
    with gzip.open(partial, 'rb') as stream:
        while stream.read(1024 * 1024):
            pass
    require(not archive.exists(), 'Final archive already exists')
    partial.rename(archive)
    sha = digest(archive)
    (run / (archive.name + '.sha256')).write_text(f'{sha}  {archive.name}\n', encoding='ascii')
    receipt = {'schema_version': 1, 'base': str(base), 'archive': archive.name,
               'sha256': sha, 'bundle_sha256': digest(bundle), 'source_bytes': logical_bytes,
               'verified_symlinks': links, 'restoration_verified': True,
               'git_recovery_verified': True, 'cleanup_completed': False}
    save(run / 'validation.json', receipt)
    print(json.dumps(receipt, indent=2), flush=True)
    return run


def confined_remove(path, parent):
    require(not path.is_symlink() and path.resolve().parent == parent.resolve(),
            f'Refusing an unconfined recursive removal: {path}')
    shutil.rmtree(path)


def cleanup(base, run):
    destination = base / 'projects-archive'
    require(run.parent.resolve() == destination.resolve() and not run.is_symlink() and
            run.name.startswith('pascal-suite-python-'), 'Invalid archive run path')
    receipt = json.loads((run / 'validation.json').read_text(encoding='utf-8'))
    require(receipt['base'] == str(base) and receipt['restoration_verified'] is True and
            receipt['git_recovery_verified'] is True and not receipt['cleanup_completed'],
            'Invalid or already consumed validation record')
    require(receipt['archive'] == PREFIX + '.tar.gz', 'Unexpected archive name')
    archive = run / receipt['archive']
    require(digest(archive) == receipt['sha256'], 'Archive checksum mismatch')
    # A receipt alone never authorizes deletion: repeat recovery from the archive.
    tree = extract_checked(archive, run / ('cleanup-restore-' + uuid.uuid4().hex[:8]))
    archived_manifests = json.loads((tree / 'source-manifests.json').read_text(encoding='utf-8'))
    require(set(archived_manifests) == set(ROOTS), 'Unexpected source inventory')
    for label, expected in archived_manifests.items():
        ensure_equal(snapshot(tree / label), expected, 'freshly restored ' + label)
    require(digest(tree / 'repository.bundle') == receipt['bundle_sha256'], 'Bundle changed')
    restore_links(tree, base, archived_manifests)
    recover_git(tree)
    jobs_and_processes(base)
    inspect_repo(base)
    for label, expected in archived_manifests.items():
        ensure_equal(snapshot(base / ROOTS[label]), expected, 'pre-cleanup ' + label)
    repo = base / 'pascal-suite-python'
    events = []
    for name in WORKTREES:
        wt = base / ROOTS['worktrees'] / name
        require(wt.parent == base / ROOTS['worktrees'] and not wt.is_symlink(), 'Unsafe worktree path')
        # --force permits the ignored logs/results already restored and hashed.
        git(repo, 'worktree', 'remove', '--force', wt)
        events.append('git worktree remove: ' + str(wt))
        save(run / 'cleanup-progress.json', events)
    remaining = git(repo, 'worktree', 'list', '--porcelain')
    require(sum(line.startswith('worktree ') for line in remaining.splitlines()) == 1,
            'Unexpected registrations remain; stop cleanup')
    parent = base / ROOTS['worktrees']
    if not any(parent.iterdir()):
        parent.rmdir()
        events.append('Removed empty worktrees parent')
    else:
        events.append('Retained nonempty worktrees parent for manual review')
    for label in ['sync-backups', 'evidence', 'history']:
        source = base / ROOTS[label]
        ensure_equal(snapshot(source), archived_manifests[label], 'last check ' + label)
        confined_remove(source, base)
        events.append('Removed preserved source: ' + str(source))
        save(run / 'cleanup-progress.json', events)
    require(git(repo, 'rev-parse', 'HEAD') == MAIN and
            git(repo, 'symbolic-ref', '--short', 'HEAD') == 'main', 'Main identity changed')
    require(not git(repo, 'status', '--porcelain=v1', '--untracked-files=all'), 'Main is dirty')
    require(digest(archive) == receipt['sha256'], 'Final archive checksum mismatch')
    receipt.update(cleanup_completed=True, cleanup_events=events, main_head=MAIN,
                   final_worktrees=remaining, archive_bytes=archive.stat().st_size)
    save(run / 'validation.json', receipt)
    for temporary in [run / 'restore-test', tree.parent]:
        confined_remove(temporary, run)
    print(json.dumps(receipt, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'cleanup'])
    parser.add_argument('--run', type=Path)
    args = parser.parse_args()
    require(sys.version_info >= (3, 13), 'Use the existing Python 3.13 environment')
    require(os.name == 'posix', 'Production execution is intended for Linux NPAD')
    os.umask(0o077)
    require(BASE.resolve() == BASE and BASE.is_dir(), 'Unexpected home path resolution')
    if args.action == 'prepare':
        require(args.run is None, 'prepare chooses an exclusive new run directory')
        run = prepare(BASE)
        print('\nVALIDATED_RUN=' + str(run))
        print('Next: invoke cleanup --run with that exact path; no sources were removed.')
    else:
        require(args.run is not None and args.run.is_absolute(), 'An absolute --run path is required')
        cleanup(BASE, args.run)


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError, tarfile.TarError) as error:
        print(f'STOP: {error}', file=sys.stderr)
        print('Inspect the saved run. No subsequent cleanup steps were executed.', file=sys.stderr)
        sys.exit(1)
