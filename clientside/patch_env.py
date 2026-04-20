from pathlib import Path

base = Path('microservices')
files = {
    'Transactions/src/index.js': '../.env',
    'Bettor/src/index.js': '../.env',
    'Client/src/index.js': '../.env',
    'Game/src/index.js': '../.env',
    'Timer/src/lib/redisClient.js': '../../.env',
    'Timer/src/lib/dbFlush.js': '../../.env',
    'Bettor/src/lib/dbFlush.js': '../../.env',
    'Timer/src/index.js': '../.env',
    'Bettor/src/lib/database.js': '../../.env',
    'stats/src/index.js': '../.env',
    'demomoney/src/index.js': '../.env',
    'StoneThrowOutcomes/src/index.js': '../.env',
    'Odds/src/lib/dbFlush.js': '../../.env',
    'Odds/src/index.js': '../.env',
    'clientupdate/src/index.js': '../.env',
    'Statistics/src/index.js': '../.env',
    'Game/src/lib/dbFlush.js': '../../.env',
    'Game/src/lib/redisClient.js': '../../.env',
}

for rel, env_rel in files.items():
    path = base / rel
    text = path.read_text(encoding='utf-8')
    old = 'require("dotenv").config({ quiet: true });'
    if old not in text:
        raise SystemExit(f'Missing target in {path}')
    new_block = (
        "const path = require('path');\n"
        "require(\"dotenv\").config({\n"
        f"  path: path.resolve(__dirname, '{env_rel}'),\n"
        "  quiet: true,\n"
        "  override: true,\n"
        "});"
    )
    text = text.replace(old, new_block)
    if "const path = require('path');\nconst path = require('path');\n" in text:
        text = text.replace("const path = require('path');\nconst path = require('path');\n", "const path = require('path');\n")
    path.write_text(text, encoding='utf-8')
    print(f'Patched {path}')
