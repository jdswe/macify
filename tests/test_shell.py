"""Pruebas dentro de un GNOME Shell aislado (tests/shell). Tardan unos minutos, así que sólo
corren si se piden: MACIFY_SHELL_TESTS=1 python3 -m unittest tests.test_shell"""

import os
import subprocess
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


@unittest.skipUnless(os.environ.get("MACIFY_SHELL_TESTS") == "1", "set MACIFY_SHELL_TESTS=1 to run")
class ShellTests(unittest.TestCase):
    def test_every_monitor_layout(self):
        result = subprocess.run([str(HERE / "shell" / "matrix.sh")], capture_output=True, text=True, timeout=1800)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
