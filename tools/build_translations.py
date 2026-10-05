"""Extract gettext strings and compile committed translation catalogs."""
from pathlib import Path
from babel.messages import frontend

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    import os
    os.chdir(ROOT)
    frontend.CommandLineInterface().run(['pybabel', 'extract', '-F', 'babel.cfg', '-o', 'translations/messages.pot', '.'])
    frontend.CommandLineInterface().run(['pybabel', 'compile', '-d', 'translations'])
