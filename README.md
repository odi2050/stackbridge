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
- amélioration IA facultative, individuelle ou pour tous les documents ;
- découpage IA tenant compte des titres, listes, tableaux et blocs de code ;
- API OpenAI-compatible, configuration personnalisée et preset Ollama ;
- token BookStack administrateur par défaut ;
- token API BookStack personnel facultatif pour la traçabilité des imports ;
- authentification OIDC/Keycloak facultative avec Authorization Code + PKCE S256 ;
- fallback local facultatif si le fournisseur OIDC est indisponible ;
- support d'un reverse proxy avec sous-chemin, par exemple `/import-document` ;
- support des certificats signés par une PKI interne via le trust store du conteneur ;
- chiffrement Fernet des secrets administrateur ;
- Docker/Compose et fonctionnement adapté aux réseaux isolés.

Le guide détaillé se trouve dans [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md).

## Installation Docker — recommandée

### Image par défaut : `latest`

L'installation standard utilise :

```text
odi2050/stackbridge:latest
```

Le `docker-compose.yml` utilise `${APP_VERSION:-latest}`. Une version précise ne doit être définie que si vous souhaitez volontairement figer le déploiement.

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

L'installation Docker est la méthode la plus simple en environnement isolé : les dépendances Python, Tesseract, Pandoc, LibreOffice et le magasin CA nécessaire sont transportés dans l'image Docker.

### 1. Sur un PC connecté à Internet

```bash
docker pull odi2050/stackbridge:latest
docker save -o stackbridge-latest.tar odi2050/stackbridge:latest
git clone https://github.com/odi2050/stackbridge.git
```

Transférez sur le réseau isolé :

- `stackbridge-latest.tar` ;
- le dossier `stackbridge/` contenant notamment `docker-compose.yml` et les scripts ;
- si nécessaire, les certificats publics de votre AC interne au format `.crt`.

### 2. Sur le serveur hors ligne

```bash
docker load -i stackbridge-latest.tar
cd stackbridge
docker run --rm -it -v "$PWD:/config" odi2050/stackbridge:latest \
  python /app/scripts/setup_env.py --output /config/.env
docker compose up -d --pull never
docker compose ps
```

`--pull never` est recommandé en air gap afin que Docker utilise explicitement l'image locale.

Ne supprimez pas `.env`, `data/` ou la clé de chiffrement pendant une mise à jour.

## Mise à jour Docker connectée

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

```env
APP_VERSION=1.1.0
```

Puis :

```bash
docker compose pull
docker compose up -d
```

Pour revenir au comportement recommandé :

```env
APP_VERSION=latest
```

## Configuration BookStack

Dans **Administration > Connexion BookStack**, renseignez l'URL de BookStack, le Token ID et le Token Secret du compte de service utilisé par défaut.

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

Pour une installation à la racine, le client Keycloak doit autoriser une Redirect URI de la forme :

```text
https://VOTRE_STACKBRIDGE/auth/oidc/callback
```

Pour un déploiement sous `/import-document` :

```text
https://bookstack.exemple.fr/import-document/auth/oidc/callback
```

L'URI réellement générée est affichée directement dans l'administration StackBridge.

StackBridge utilise Authorization Code + PKCE S256. Les claims `sub`, nom/username et email servent à identifier l'utilisateur et à enrichir la journalisation des imports.

**Important :** le jeton OIDC Keycloak ne remplace pas le Token ID/Token Secret de l'API BookStack. Pour la traçabilité BookStack des créations, utilisez le token API personnel.

### Fallback local

Le fallback est prévu pour éviter un verrouillage lorsque Keycloak est indisponible. Lorsqu'il est autorisé, la page de connexion propose **Continuer en mode local** et l'utilisation de ce mode est journalisée.

## Reverse proxy avec `/import-document`

StackBridge peut être publié derrière le même nom DNS que BookStack :

```text
https://bookstack.exemple.fr/                 -> BookStack
https://bookstack.exemple.fr/import-document/ -> StackBridge
```

Dans `.env` :

```env
SESSION_COOKIE_SECURE=true
TRUST_PROXY_HEADERS=true
```

Exemple Apache HTTP Server :

```apache
ProxyPreserveHost On

ProxyPass        /import-document/ http://127.0.0.1:5050/
ProxyPassReverse /import-document/ http://127.0.0.1:5050/

<Location /import-document/>
    RequestHeader set X-Forwarded-Proto "https"
    RequestHeader set X-Forwarded-Prefix "/import-document"
</Location>
```

La règle `/import-document/` doit précéder une éventuelle règle `ProxyPass / ...` plus générale.

`TRUST_PROXY_HEADERS=true` doit seulement être activé derrière un proxy de confiance. Si le port `5050` est accessible directement depuis le réseau, filtrez cet accès avec un pare-feu ou limitez-le au reverse proxy.

StackBridge utilise alors le préfixe transmis pour ses ressources statiques, ses appels API, l'administration, les redirections après connexion et le callback OIDC.

## Certificats locaux / PKI interne

Si Keycloak utilise un certificat signé par votre PKI interne, gardez **Vérifier les certificats SSL/TLS** activé.

Placez uniquement les certificats publics de l'AC racine et des éventuelles AC intermédiaires dans :

```text
stackbridge/
└── certs/
    ├── root-ca.crt
    └── intermediate-ca.crt
```

Les fichiers doivent être au format PEM avec l'extension `.crt`. Ne copiez jamais une clé privée dans ce dossier.

Le `docker-compose.yml` monte automatiquement `./certs` dans le magasin CA local du conteneur. Au démarrage, StackBridge lance `update-ca-certificates` et utilise ensuite `/etc/ssl/certs/ca-certificates.crt` pour ses connexions HTTPS, notamment :

- découverte OIDC ;
- endpoint token ;
- endpoint `userinfo` ;
- autres appels Python `requests` qui utilisent le bundle système.

Après ajout ou remplacement d'un certificat :

```bash
docker compose up -d --force-recreate
```

Le dossier `certs/` est exclu de Git et du contexte de build Docker afin d'éviter d'embarquer accidentellement des certificats internes dans le dépôt ou dans l'image publique.

## Documents, PDF et OCR

StackBridge accepte DOCX, PDF, Markdown, HTML, TXT et ZIP. Les fichiers peuvent être sélectionnés ou glissés-déposés. Une confirmation visuelle affiche le nombre de documents réellement chargés.

Pour une arborescence de dossiers, utilisez un ZIP. Les chemins internes peuvent devenir des chapitres BookStack.

Le moteur PDF V2 décide page par page entre extraction native et OCR. Une page scannée reste représentée par son rendu original même lorsque Tesseract ne produit pas de texte exploitable.

## Amélioration IA

L'IA est optionnelle. Configurez le service dans Administration puis activez-la dans l'importateur.

Les gros documents sont découpés en blocs en préservant autant que possible titres, tableaux, listes et code. La version originale reste disponible.

Les images Base64 sont masquées par défaut avant l'appel au modèle puis restaurées. `AI_MAX_INPUT_TOKENS` vaut `3000` par défaut dans l'image Docker.

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

Pour une PKI interne sans Docker, vous pouvez définir `REQUESTS_CA_BUNDLE` vers un bundle PEM de confiance avant de lancer StackBridge.

## Construction locale de l'image

```bash
git clone https://github.com/odi2050/stackbridge.git
cd stackbridge
docker build --build-arg APP_VERSION=dev -t stackbridge:dev .
```

Le dossier local `certs/` est ignoré par le contexte Docker et n'est donc pas inclus dans l'image.

L'installation utilisateur normale doit privilégier `odi2050/stackbridge:latest`.

## Documentation

- Guide détaillé StackBridge : [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md)
- Documentation BookStack OIDC : https://www.bookstackapp.com/docs/admin/oidc-auth/
- Documentation BookStack : https://www.bookstackapp.com/docs/

## Licence

StackBridge est publié sous licence MIT. Voir `LICENSE`.

## Notes

Le cache de prévisualisation est conservé en mémoire et disparaît lors du redémarrage de StackBridge.
