import argparse
import getpass
import secrets
from pathlib import Path
from cryptography.fernet import Fernet
from werkzeug.security import generate_password_hash

parser=argparse.ArgumentParser(description="Génère la configuration initiale sécurisée de StackBridge")
parser.add_argument("--output",default=".env",help="Fichier .env à créer")
parser.add_argument("--force",action="store_true",help="Remplacer un fichier existant")
args=parser.parse_args();output=Path(args.output)
if output.exists() and not args.force:raise SystemExit(f"{output} existe déjà. Utilisez --force pour le remplacer.")
password=getpass.getpass("Nouveau mot de passe administrateur (12 caractères minimum) : ")
confirmation=getpass.getpass("Confirmez le mot de passe : ")
if password!=confirmation:raise SystemExit("Les mots de passe ne correspondent pas.")
if len(password)<12:raise SystemExit("Le mot de passe doit contenir au moins 12 caractères.")
version=(Path(__file__).resolve().parent.parent/"VERSION").read_text(encoding="utf-8").strip()
content=f"""APP_VERSION={version}
ADMIN_PASSWORD_HASH='{generate_password_hash(password,method='scrypt')}'
SECRET_KEY={secrets.token_hex(32)}
SETTINGS_ENCRYPTION_KEY={Fernet.generate_key().decode()}
SESSION_COOKIE_SECURE=false
"""
output.parent.mkdir(parents=True,exist_ok=True);output.write_text(content,encoding="utf-8")
print(f"Configuration créée dans {output}. Protégez ce fichier et ne le publiez jamais.")
