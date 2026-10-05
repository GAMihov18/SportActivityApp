"""Build the Bulgarian PO catalog from the editable initial translation map."""
import json
from pathlib import Path
from babel.messages.catalog import Catalog
from babel.messages.pofile import write_po
from babel.messages.mofile import write_mo

root = Path(__file__).resolve().parents[1]
messages = json.loads((root / 'translations/bg.json').read_text(encoding='utf-8'))
catalog = Catalog(locale='bg', project='Stride', version='1.0')
catalog.fuzzy = False
for original, translation in messages.items():
    catalog.add(original, translation)
directory = root / 'translations/bg/LC_MESSAGES'
directory.mkdir(parents=True, exist_ok=True)
with (directory / 'messages.po').open('wb') as stream:
    write_po(stream, catalog, width=100)
with (directory / 'messages.mo').open('wb') as stream:
    write_mo(stream, catalog)
