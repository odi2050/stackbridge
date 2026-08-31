import re
import os
import sys
from pathlib import Path

root=Path(__file__).resolve().parent.parent
version=(root/"VERSION").read_text(encoding="utf-8").strip()
if not re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?",version):sys.exit(f"VERSION invalide : {version}")
configured=os.getenv("APP_VERSION","").strip()
if not configured:
 env_file=root/".env"
 if not env_file.exists():sys.exit("Fichier .env absent. Copiez .env.example vers .env.")
 match=re.search(r"(?m)^APP_VERSION=(.+)$",env_file.read_text(encoding="utf-8"))
 if not match:sys.exit("APP_VERSION absent de .env")
 configured=match.group(1).strip()
if configured!=version:sys.exit(f"Versions incohérentes : VERSION={version}, .env={configured}")
changelog=(root/"CHANGELOG.md").read_text(encoding="utf-8")
if f"## [{version}]" not in changelog:sys.exit(f"CHANGELOG.md ne contient pas de section [{version}]")
print(f"StackBridge {version} : release cohérente")
