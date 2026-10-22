"""Start the interface from an installed copy or a checkout: python run.py [--hidden].

Running a file (rather than `python -m`) puts this folder first on the import
path, so a vpngo_gui folder in the current directory can never shadow it.
"""

import sys

from vpngo_gui.__main__ import main

sys.exit(main())
