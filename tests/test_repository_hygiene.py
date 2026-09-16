from pathlib import Path
import unittest


class RepositoryHygieneTests(unittest.TestCase):
    def test_archived_duplicate_tree_is_not_on_main(self):
        root = Path(__file__).resolve().parents[1]
        self.assertFalse((root / 'repo_from_git').exists())

    def test_temporary_squash_artifacts_are_not_tracked_in_worktree(self):
        root = Path(__file__).resolve().parents[1]
        forbidden_names = {'__squash_note__.txt', 'tmp-squash-note.txt'}
        forbidden_suffixes = {'.tmp', '.squash'}

        offenders = []
        for path in root.rglob('*'):
            if not path.is_file():
                continue
            relative = path.relative_to(root)
            if '.git' in relative.parts:
                continue
            if path.name in forbidden_names or path.suffix in forbidden_suffixes:
                offenders.append(str(relative))

        self.assertEqual(offenders, [], f'Unexpected temporary artifacts: {offenders}')


if __name__ == '__main__':
    unittest.main()
