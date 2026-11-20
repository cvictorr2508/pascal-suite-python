"""Synthetic local recovery tests; no access to NPAD or scientific evidence."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import npad_archive_pascal as archive

TEST_TMP = Path(__file__).resolve().parent / 'test-tmp'
if os.name == 'nt':
    TEST_TMP = Path('\\\\?\\' + str(Path(__file__).resolve().parents[1] / 't'))
TEST_TMP.mkdir(exist_ok=True)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        if os.name == 'nt':
            original_command = archive.command

            def long_path_git(args, cwd=None):
                args = [str(value).removeprefix('\\\\?\\') for value in args]
                if cwd is not None:
                    cwd = str(cwd).removeprefix('\\\\?\\')
                if str(args[0]) == 'git':
                    args = ['git', '-c', 'core.longpaths=true', *args[1:]]
                return original_command(args, cwd)

            patcher = patch.object(archive, 'command', side_effect=long_path_git)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.temp = tempfile.TemporaryDirectory(dir=TEST_TMP)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / 'pascal-suite-python'
        self.repo.mkdir()
        archive.command(['git', 'init', '--quiet', '--initial-branch=main', self.repo])
        archive.git(self.repo, 'config', 'user.name', 'Synthetic Recovery Test')
        archive.git(self.repo, 'config', 'user.email', 'fixture@example.invalid')
        archive.git(self.repo, 'config', 'commit.gpgsign', 'false')
        (self.repo / '.gitignore').write_text('ignored/\n*.log\nresultados_finais/\n')
        (self.repo / 'tracked.txt').write_text('scientific source fixture\n')
        archive.git(self.repo, 'add', '.')
        archive.git(self.repo, 'commit', '--quiet', '-m', 'Synthetic baseline')
        archive.git(self.repo, 'remote', 'add', 'origin',
                    'git@github.com:cvictorr2508/pascal-suite-python.git')
        first = archive.git(self.repo, 'rev-parse', 'HEAD')
        (self.repo / 'tracked.txt').write_text('second historical source\n')
        archive.git(self.repo, 'commit', '--quiet', '-am', 'Historical second commit')
        second = archive.git(self.repo, 'rev-parse', 'HEAD')
        (self.repo / 'tracked.txt').write_text('current main source\n')
        archive.git(self.repo, 'commit', '--quiet', '-am', 'Current main commit')
        sha = archive.git(self.repo, 'rev-parse', 'HEAD')
        self.worktrees = {'detached': first, 'branched': second}
        parent = self.base / archive.ROOTS['worktrees']
        parent.mkdir()
        for i, (name, tip) in enumerate(self.worktrees.items()):
            wt = parent / name
            flags = ['--detach'] if i == 0 else ['-b', 'fixture-validation']
            archive.git(self.repo, 'worktree', 'add', '--quiet', *flags, wt, tip)
            (wt / 'ignored').mkdir()
            (wt / 'ignored' / 'solver.log').write_text('ignored but irreplaceable log\n')
            (wt / 'resultados_finais').mkdir()
            (wt / 'resultados_finais' / 'meta.json').write_text('{"fixture": true}\n')
        for label in ['evidence', 'history', 'sync-backups']:
            root = self.base / archive.ROOTS[label]
            root.mkdir()
            (root / (label + '.txt')).write_text(label + ' preserved\n')
        (self.base / 'projects-archive').mkdir()
        (self.base / 'projects-archive' / 'other-project.keep').write_text('untouched\n')
        self.originals = {label: archive.snapshot(self.base / source)
                          for label, source in archive.ROOTS.items()}
        self.patches = [patch.object(archive, 'MAIN', sha),
                        patch.object(archive, 'WORKTREES', self.worktrees),
                        patch.object(archive, 'jobs_and_processes'),
                        patch.object(archive.os, 'getuid', return_value=0, create=True)]
        if os.name == 'posix':
            self.patches[-1] = patch.object(archive.os, 'getuid', return_value=os.getuid())
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def prepare(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return archive.prepare(self.base)

    def test_prepare_recovers_detached_and_branched_trees_with_ignored_results(self):
        run = self.prepare()
        receipt = json.loads((run / 'validation.json').read_text())
        self.assertTrue(receipt['restoration_verified'])
        self.assertTrue(receipt['git_recovery_verified'])
        self.assertFalse(receipt['cleanup_completed'])
        for label, expected in self.originals.items():
            self.assertEqual(archive.snapshot(self.base / archive.ROOTS[label]), expected)
        for name in self.worktrees:
            wt = run / 'restore-test' / archive.PREFIX / 'worktrees' / name
            self.assertTrue((wt / '.git').is_dir())
            self.assertEqual((wt / 'ignored/solver.log').read_text(), 'ignored but irreplaceable log\n')
            self.assertTrue((wt / 'resultados_finais/meta.json').is_file())
        self.assertEqual((self.base / 'projects-archive/other-project.keep').read_text(), 'untouched\n')

    def test_source_change_blocks_cleanup_before_any_removal(self):
        run = self.prepare()
        root = self.base / archive.ROOTS['evidence']
        (root / 'new-result.txt').write_text('arrived after preservation\n')
        with self.assertRaisesRegex(RuntimeError, 'pre-cleanup evidence'):
            with contextlib.redirect_stdout(io.StringIO()):
                archive.cleanup(self.base, run)
        for source in archive.ROOTS.values():
            self.assertTrue((self.base / source).exists())

    def test_corrupted_archive_blocks_cleanup(self):
        run = self.prepare()
        target = run / (archive.PREFIX + '.tar.gz')
        with target.open('ab') as stream:
            stream.write(b'tampered')
        with self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
            archive.cleanup(self.base, run)
        self.assertTrue((self.base / archive.ROOTS['sync-backups']).exists())

    def test_locked_worktree_blocks_preparation(self):
        wt = self.base / archive.ROOTS['worktrees'] / next(iter(self.worktrees))
        archive.git(self.repo, 'worktree', 'lock', wt)
        with self.assertRaisesRegex(RuntimeError, 'locked'):
            self.prepare()

    def test_tracked_change_blocks_preparation(self):
        wt = self.base / archive.ROOTS['worktrees'] / next(iter(self.worktrees))
        (wt / 'tracked.txt').write_text('uncommitted change\n')
        with self.assertRaisesRegex(RuntimeError, 'require review'):
            self.prepare()

    def test_extraction_rejects_path_traversal(self):
        target = self.base / 'bad.tar.gz'
        with tarfile.open(target, 'w:gz') as tar:
            member = tarfile.TarInfo('../escape.txt')
            member.size = 1
            tar.addfile(member, io.BytesIO(b'x'))
        with self.assertRaisesRegex(RuntimeError, 'Unsafe archive member'):
            archive.extract_checked(target, self.base / 'restore-bad')
        self.assertFalse((self.base / 'escape.txt').exists())

    def test_recursive_removal_rejects_parent_and_outside_paths(self):
        with self.assertRaisesRegex(RuntimeError, 'unconfined'):
            archive.confined_remove(self.base, self.base)
        self.assertTrue(self.repo.exists())

    @unittest.skipUnless(os.name == 'posix', 'Linux deletion semantics; production is Linux-only')
    def test_full_cleanup_removes_only_verified_roots_and_keeps_main(self):
        run = self.prepare()
        with contextlib.redirect_stdout(io.StringIO()):
            archive.cleanup(self.base, run)
        for label in ['evidence', 'worktrees', 'history', 'sync-backups']:
            self.assertFalse((self.base / archive.ROOTS[label]).exists())
        self.assertTrue((self.repo / '.git').is_dir())
        self.assertTrue((run / (archive.PREFIX + '.tar.gz')).is_file())
        self.assertTrue(json.loads((run / 'validation.json').read_text())['cleanup_completed'])
        self.assertTrue((self.base / 'projects-archive/other-project.keep').exists())

    def test_internal_link_relocation_is_independent_of_original_tree(self):
        root = self.base / archive.ROOTS['evidence']
        try:
            (root / 'link.txt').symlink_to(root / 'evidence.txt')
        except OSError as error:
            self.skipTest(f'Local symlink creation unavailable: {error}')
        run = self.prepare()
        restored = run / 'restore-test' / archive.PREFIX / 'evidence'
        (root / 'evidence.txt').write_text('changed original after recovery\n')
        self.assertEqual((restored / 'link.txt').read_text(), 'evidence preserved\n')
        self.assertFalse(os.path.isabs(os.readlink(restored / 'link.txt')))


if __name__ == '__main__':
    unittest.main(verbosity=2)
