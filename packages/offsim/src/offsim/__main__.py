"""``python -m offsim`` is the same as the ``offsim`` command."""

import sys

from .cli import main

sys.exit(main())
