# StackBridge — BookStack Document Importer

**StackBridge est un importateur de documents open-source et auto-hébergé pour BookStack. Il convertit et importe DOCX/Word, PDF, Markdown, HTML et TXT avec OCR, prévisualisation, structure dossiers → chapitres et amélioration IA optionnelle.**

## Fonctionnalités

- import DOCX / Microsoft Word vers BookStack ;
- moteur PDF V2 avec extraction native PyMuPDF et OCR Tesseract pour les scans ;
- conservation de la page originale en cas d'échec OCR ;
- Markdown, HTML et TXT ;
- import multiple et glisser-déposer avec confirmation visuelle des fichiers chargés ;
- ZIP avec conversion de l'arborescence en chapitres BookStack ;
- prévisualisation avant publication ;
- amélioration IA facultative, individuelle ou séquentielle pour tous les documents ;
- découpage IA tenant compte des titres, listes, tableaux et blocs de code ;
- choix global entre version originale et version IA ;
- API OpenAI-compatible, configuration personnalisée et preset Ollama ;
- token BookStack administrateur par défaut ;
- token API BookStack personnel facultatif pour la traçabilité des imports ;
- authentification OIDC/Keycloak facultative avec Authorization Code + PKCE S256 ;
- configuration OIDC directement dans le panneau Administration ;
- fallback local facultatif si le fournisseur OIDC est indisponible ;
- chiffrement Fernet des secrets administrateur ;
- Docker/Compose et fonctionnement adapté aux réseaux isolés.

Le guide détaillé des fonctions et de leur configuration se trouve dans [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md).

## Installation Docker — recommandée

### Image par défaut : `latest`

L'installation standard utilise toujours :

```text
odi2050/stackbridge:latest
```

Le `docker-compose.yml` utilise `${APP_VERSION:-latest}` et le générateur de `.env` écrit désormais `APP_VERSION=latest`. Ainsi, **`latest` reste le choix mis en avant et utilisé par défaut**.

Une version précise ne doit être définie que si vous souhaitez volontairement figer le déploiement.

### Prérequis

- Docker Engine ou Docker Desktop avec Compose v2 ;
- Git pour récupérer les fichiers de déploiement ;
- port TCP `5050` disponible ;
- accès réseau à BookStack ;
- accès à Keycloak uniquement si OIDC est activé ;
- accès au service IA uniquement si l'amélioration IA est utilisée.

### Installation en ligne

```bash
git clone https://github.com/odi2050/stackbridge.git
cd stackbridge
docker pull odi2050/stackbridge:latest
```

Générez ensuite `.env`.

Linux/macOS :

```bash
docker run --rm -it -v "$PWD:/config" odi2050/stackbridge:latest \
  python /app/scripts/setup_env.py --output /config/.env
```

PowerShell :

```powershell
docker run --rm -it -v "${PWD}:/config" odi2050/stackbridge:latest `
  python /app/scripts/setup_env.py --output /config/.env
```

Démarrez :

```bash
docker compose up -d
docker compose ps
```

Ouvrez ensuite `http://ADRESSE_DU_SERVEUR:5050`. Le panneau d'administration est disponible sur `/admin`.

## Installation hors ligne / Air Gap

L'installation Docker est la méthode la plus simple en environnement isolé : **toutes les dépendances Python, Tesseract, Pandoc et LibreOffice nécessaires au conteneur sont transportées dans l'image Docker**.

### 1. Sur un PC connecté à Internet

Récupérez la dernière image :

```bash
docker pull odi2050/stackbridge:latest
```

Exportez-la :

```bash
docker save -o stackbridge-latest.tar odi2050/stackbridge:latest
```

Récupérez également les fichiers de déploiement :

```bash
git clone https://github.com/odi2050/stackbridge.git
```

Transférez sur le réseau isolé :

- `stackbridge-latest.tar` ;
- le dossier `stackbridge/` contenant notamment `docker-compose.yml` et les scripts.

### 2. Sur le serveur hors ligne

Chargez l'image :

```bash
docker load -i stackbridge-latest.tar
```

Vérifiez :

```bash
docker image ls odi2050/stackbridge
```

Placez-vous dans le dossier StackBridge puis générez `.env` **sans accès Internet** grâce au script déjà présent dans l'image :

```bash
docker run --rm -it -v "$PWD:/config" odi2050/stackbridge:latest \
  python /app/scripts/setup_env.py --output /config/.env
```

Démarrez ensuite sans demander de téléchargement :

```bash
docker compose up -d --pull never
docker compose ps
```

`--pull never` est recommandé en air gap afin que Docker utilise explicitement l'image locale.

### Mise à jour d'un environnement hors ligne

Sur le poste connecté :

```bash
docker pull odi2050/stackbridge:latest
docker save -o stackbridge-latest.tar odi2050/stackbridge:latest
```

Transférez le nouveau TAR et, si nécessaire, les nouveaux fichiers du dépôt. Sur le serveur isolé :

```bash
docker compose down
docker load -i stackbridge-latest.tar
docker compose up -d --pull never
```

Ne supprimez pas `.env`, `data/` ou la clé de chiffrement pendant une mise à jour.

## Mise à jour Docker connectée

Puisque `latest` est le comportement par défaut :

```bash
git pull
docker compose pull
docker compose up -d
```

Pour vérifier l'image utilisée :

```bash
docker compose images
```

### Figer volontairement une version

Modifiez `.env`, par exemple :

```env
APP_VERSION=1.0.0
```

Puis :

```bash
docker compose pull
docker compose up -d
```

Pour revenir au fonctionnement recommandé :

```env
APP_VERSION=latest
```

## Configuration BookStack

Dans **Administration > Connexion BookStack**, renseignez l'URL de BookStack, le Token ID et le Token Secret du compte de service utilisé par défaut.

Les utilisateurs qui ne demandent rien de particulier utilisent cette configuration administrateur.

### Token personnel et traçabilité

Un utilisateur peut activer **Utiliser mon token API BookStack personnel** dans l'importateur. Les requêtes sont alors effectuées avec les permissions du compte BookStack ayant créé ce token, ce qui permet d'attribuer les créations au bon utilisateur côté BookStack.

Dans BookStack :

1. ouvrir **Mon compte / My Account** ;
2. ouvrir **Accès et sécurité / Access & Security** ;
3. créer un token dans **API Tokens**, par exemple `StackBridge` ;
4. copier immédiatement le Token ID et le Token Secret ;
5. les saisir dans StackBridge puis cliquer sur **Charger les livres**.

Le secret n'est affiché qu'une fois par BookStack. Si API Tokens n'est pas disponible, le rôle doit disposer de la permission **Access System API**.

## OIDC / Keycloak

OIDC est entièrement facultatif et se configure dans **Administration > Authentification OIDC / Keycloak**.

Renseignez :

- Issuer URL ;
- Client ID ;
- Client Secret si nécessaire ;
- scopes, généralement `openid profile email` ;
- nom d'affichage du SSO ;
- activation ou non du fallback local.

Utilisez **Tester la configuration OIDC** avant l'activation. StackBridge interroge :

```text
<issuer>/.well-known/openid-configuration
```

Le client Keycloak doit autoriser la Redirect URI :

```text
https://VOTRE_STACKBRIDGE/auth/oidc/callback
```

StackBridge utilise Authorization Code + PKCE S256. Les claims `sub`, nom/username et email servent à identifier l'utilisateur et à enrichir la journalisation des imports.

**Important :** le jeton OIDC Keycloak ne remplace pas le Token ID/Token Secret de l'API BookStack. Pour la traçabilité BookStack des créations, utilisez le token API personnel.

### Fallback local

Le fallback est prévu pour éviter un verrouillage lorsque Keycloak est indisponible. Lorsqu'il est autorisé, la page de connexion propose **Continuer en mode local** et l'utilisation de ce mode est journalisée.

Il est conseillé de le laisser activé pendant la mise en service OIDC. Il peut ensuite être désactivé si la politique de sécurité impose exclusivement l'authentification centralisée.

## Documents, PDF et OCR

StackBridge accepte DOCX, PDF, Markdown, HTML, TXT et ZIP. Les fichiers peuvent être sélectionnés ou glissés-déposés. Une confirmation visuelle affiche le nombre de documents réellement chargés.

Pour une arborescence de dossiers, utilisez un ZIP. Les chemins internes peuvent devenir des chapitres BookStack.

Le moteur PDF V2 décide page par page entre extraction native et OCR. Une page scannée reste représentée par son rendu original même lorsque Tesseract ne produit pas de texte exploitable.

## Amélioration IA

L'IA est optionnelle. Configurez le service dans Administration puis activez-la dans l'importateur.

Les gros documents sont découpés en blocs en préservant autant que possible titres, tableaux, listes et code. **Améliorer tous les fichiers** traite les documents séquentiellement pour limiter la charge. La version originale reste disponible.

Les images Base64 sont masquées par défaut avant l'appel au modèle puis restaurées. Cela réduit fortement la consommation du contexte. `AI_MAX_INPUT_TOKENS` vaut `6000` par défaut.

## Sécurité et données persistantes

Les secrets administrateur sont chiffrés avec Fernet dans `data/settings.json`, notamment les identifiants BookStack, la clé IA et le Client Secret OIDC.

Sauvegardez :

```text
.env
data/settings.json
data/admin_auth.json
data/.settings.key
```

Si `SETTINGS_ENCRYPTION_KEY` est défini dans `.env`, sauvegardez également cette valeur de manière sécurisée.

Avec un reverse proxy HTTPS :

```env
SESSION_COOKIE_SECURE=true
```

Les logs sont conservés dans `logs/app.log`. Le panneau Administration permet d'activer la journalisation détaillée et de consulter/télécharger les dernières lignes.

## Installation Python sans Docker

Python 3.12 est recommandé. Tesseract est requis pour les PDF scannés. Pandoc/LibreOffice peuvent également être nécessaires selon les conversions.

```bash
git clone https://github.com/odi2050/stackbridge.git
cd stackbridge
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python scripts/setup_env.py
python app.py
```

Sous Windows, activez le venv avec :

```powershell
.\.venv\Scripts\Activate.ps1
```

## Construction locale de l'image

Pour le développement :

```bash
git clone https://github.com/odi2050/stackbridge.git
cd stackbridge
docker build --build-arg APP_VERSION=dev -t stackbridge:dev .
```

L'installation utilisateur normale doit privilégier `odi2050/stackbridge:latest`.

## Documentation

- Guide détaillé StackBridge : [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md)
- Documentation BookStack OIDC : https://www.bookstackapp.com/docs/admin/oidc-auth/
- Documentation BookStack : https://www.bookstackapp.com/docs/

## Licence

StackBridge est publié sous licence MIT. Voir `LICENSE`.

## Notes

Le cache de prévisualisation est conservé en mémoire et disparaît lors du redémarrage de StackBridge.
