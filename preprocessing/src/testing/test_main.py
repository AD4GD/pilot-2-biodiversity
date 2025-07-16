import unittest
from unittest import TestCase
import main
import sys
import io
from contextlib import redirect_stdout
# from unittest.mock import Mock, patch

class TestMain(TestCase):
    def test_init(self):
        # capture the output
        f = io.StringIO()
        with redirect_stdout(f):
            main.init("firstname","lastname", formal=True)
        out = f.getvalue()
        self.assertEqual(out, "Hello Dr. firstname lastname\n")
        f.close()