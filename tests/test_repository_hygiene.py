from pathlib import Path
import os
import unittest


class RepositoryHygieneTests(unittest.TestCase):
    def test_archived_duplicate_tree_is_not_on_main(self):
        root = Path(__file__).resolve().parents[1]
        self.assertFalse((root / 'repo_from_git').exists())

    def test_temporary_squash_artifacts_are_not_in_project_tree(self):
        root = Path(__file__).resolve().parents[1]
        forbidden_names = {'__squash_note__.txt', 'tmp-squash-note.txt'}
        forbidden_suffixes = {'.tmp', '.squash'}
        skipped_dirs = {'.git', '.venv', 'venv', '__pycache__', '.pytest_cache'}

        offenders = []
        for directory, dirnames, filenames in os.walk(root):
            dirnames[:] = [name for name in dirnames if name not in skipped_dirs]
            base_dir = Path(directory)
            for filename in filenames:
                path = base_dir / filename
                relative = path.relative_to(root)
                if filename in forbidden_names or path.suffix in forbidden_suffixes:
                    offenders.append(str(relative))

        self.assertEqual(offenders, [], f'Unexpected temporary artifacts: {offenders}')


if __name__ == '__main__':
    unittest.main()
