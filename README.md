# StackBridge

**Document Import Studio for BookStack** — version `1.0.0`.

Import massif de documents DOCX, PDF, Markdown, HTML et TXT vers BookStack, avec structure dossiers → chapitres, OCR Tesseract, prévisualisation et amélioration IA optionnelle.

L’interface n’utilise pas la sélection native de dossier du navigateur. Pour conserver une arborescence sans confirmation Chrome, compressez le dossier en ZIP puis sélectionnez l’archive. Les chemins internes du ZIP deviennent les chapitres BookStack.

## Installation avec Docker

### Prérequis

- Docker Engine ou Docker Desktop avec Compose v2 ;
- Git pour récupérer et mettre à jour le projet ;
- port TCP `5050` disponible.

### Première installation

```bash
git clone https://github.com/odi2050/stackbridge.git
cd stackbridge
docker build --build-arg APP_VERSION=1.0.0 -t stackbridge:1.0.0 .
```

Générez ensuite le fichier `.env` de manière interactive. La commande demande le mot de passe administrateur et crée automatiquement son hash scrypt ainsi que les clés de session et de chiffrement :

Linux ou macOS :

```bash
docker run --rm -it -v "$PWD:/config" stackbridge:1.0.0 \
  python /app/scripts/setup_env.py --output /config/.env
```

PowerShell :

```powershell
docker run --rm -it -v "${PWD}:/config" stackbridge:1.0.0 `
  python /app/scripts/setup_env.py --output /config/.env
```

Démarrez enfin StackBridge :

```bash
docker compose up -d --build
docker compose ps
```

Ouvrez `http://ADRESSE_DU_SERVEUR:5050`. L’administration est disponible dans `/admin`.

Le conteneur utilise Waitress avec huit threads. Les réglages chiffrés sont persistés dans `data/` et les journaux dans `logs/`. Le healthcheck interroge `/api/health` toutes les 30 secondes.

### Mise à jour Docker

```bash
git pull
python scripts/check_release.py
docker compose build --pull
docker compose up -d
```

Avant une mise à jour majeure, sauvegardez `.env`, `data/` et `logs/`. Ne supprimez jamais `data/.settings.key` si `SETTINGS_ENCRYPTION_KEY` n’est pas défini dans `.env`.

### Arrêt et redémarrage

```bash
docker compose stop
docker compose start
docker compose restart
```

Pour retirer uniquement le conteneur tout en conservant les données :

```bash
docker compose down
```

## Versioning et releases Docker

StackBridge suit [Semantic Versioning](https://semver.org/lang/fr/) sous la forme `MAJEURE.MINEURE.CORRECTIF` :

- `MAJEURE` : changement incompatible de configuration, d’API ou de données ;
- `MINEURE` : nouvelle fonctionnalité rétrocompatible ;
- `CORRECTIF` : correction rétrocompatible.

Le fichier `VERSION` est la source de référence dans le dépôt. La même valeur doit être reportée dans `APP_VERSION` du fichier `.env` lors d’une release. Elle est ensuite :

- intégrée à l’image sous `STACKBRIDGE_VERSION` ;
- utilisée pour le tag `stackbridge:<version>` ;
- inscrite dans les labels OCI de l’image ;
- affichée dans l’interface ;
- exposée par `/api/version` et `/api/health` ;
- utilisée pour invalider proprement le cache CSS et JavaScript.

### Créer une release

1. Choisir la nouvelle version SemVer, par exemple `1.1.0`.
2. Modifier `VERSION` et `APP_VERSION` dans `.env` avec exactement la même valeur.
3. Ajouter les changements dans `CHANGELOG.md` sous une section datée.
4. Valider la cohérence : `python scripts/check_release.py`.
5. Construire l’image : `docker compose build --pull`.
6. Vérifier sa version : `docker compose run --rm stackbridge python -c "from version import APP_VERSION; print(APP_VERSION)"`.
7. Démarrer la release : `docker compose up -d`.
8. Contrôler son état : `docker compose ps` puis ouvrir `/api/health`.
9. Si le dépôt est versionné avec Git, créer un tag annoté correspondant : `git tag -a v1.1.0 -m "StackBridge 1.1.0"`.

Ne réutilisez jamais un même tag pour deux images différentes. Pour les tests intermédiaires, utilisez des préversions SemVer telles que `1.1.0-rc.1`; réservez `latest` comme alias facultatif d’une version stable déjà taguée.

## Installation directe sans Docker

### Prérequis

- Python 3.12 ou version compatible ;
- Git ;
- Tesseract OCR facultatif mais nécessaire pour les PDF scannés ;
- accès réseau à BookStack et, si utilisée, à l’API IA.

Sous Debian ou Ubuntu, Tesseract peut être installé avec :

```bash
sudo apt update
sudo apt install tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng
```

Sous Windows, installez Tesseract puis ajoutez son répertoire au `PATH`.

### Installation Linux ou macOS

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

### Installation Windows PowerShell

```powershell
git clone https://github.com/odi2050/stackbridge.git
Set-Location stackbridge
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python scripts\setup_env.py
python app.py
```

StackBridge écoute sur `0.0.0.0:5050` avec Waitress. Le fichier `.env` est chargé automatiquement au démarrage.

### Mise à jour directe

```bash
git pull
python -m pip install -r requirements.txt
python scripts/check_release.py
```

Redémarrez ensuite le processus StackBridge ou le service système qui l’exécute.

## Administration

Ouvrir `/admin` pour configurer BookStack, l’IA, la vérification TLS et les logs détaillés. La découverte des modèles interroge l’endpoint OpenAI-compatible `/v1/models` et propose une recherche dans les résultats.

- `Vérifier les certificats SSL/TLS` s’applique à tous les appels BookStack et IA.
- Les URL `http://` sont acceptées. Elles ne chiffrent pas le trafic et sont déconseillées hors réseau de confiance.
- `Journalisation détaillée globale` trace les routes, conversions, OCR, appels HTTP, IA et imports.
- Les journaux rotatifs sont écrits dans `logs/app.log` et consultables depuis l’administration.

Avant un appel IA, les images Base64 sont remplacées par de petits marqueurs puis restaurées après la réponse. Cela évite de consommer le quota de tokens avec des données d’image. `AI_MAX_INPUT_TOKENS` fixe la limite préventive du texte envoyé (6000 par défaut).

L’option administrative « Envoyer les images à l’IA » permet de désactiver ce masquage. Elle est désactivée par défaut, car l’envoi des images Base64 peut dépasser rapidement les limites de tokens du fournisseur.

### API IA personnalisée

Le mode personnalisé de l’administration permet de définir l’endpoint POST, le corps JSON et le chemin du texte dans la réponse. Les variables disponibles sont `{{model}}`, `{{system_prompt}}`, `{{prompt}}`, `{{html}}` et `{{level}}`. Les chemins de réponse utilisent une notation par points, par exemple `message.content` ou `choices.0.message.content`. Un préréglage Ollama est fourni dans l’interface.

Les tokens et clés API ne sont jamais affichés dans l’interface utilisateur. Ils sont conservés chiffrés dans `data/settings.json`, qui est exclu de Git.

Les champs sensibles de `settings.json` (`token_id`, `token_secret` et `ai_api_key`) sont chiffrés avec Fernet. Une clé locale est créée dans `data/.settings.key`; en production, utilisez plutôt `SETTINGS_ENCRYPTION_KEY` depuis un secret Docker ou une variable d’environnement. Ne perdez pas cette clé, sinon les valeurs deviennent irrécupérables.

L’administrateur peut changer son mot de passe depuis le panneau. Seul son hash scrypt est stocké dans `data/admin_auth.json`.

## Sécurité

### Protection des secrets

- Le Token ID BookStack, le Token Secret et la clé API IA sont chiffrés au repos avec Fernet dans `data/settings.json`.
- Les anciennes valeurs en clair sont migrées automatiquement au premier chargement.
- La clé locale est enregistrée dans `data/.settings.key` avec des permissions restrictives lorsque le système les prend en charge.
- En production, il est recommandé de fournir `SETTINGS_ENCRYPTION_KEY` depuis un gestionnaire de secrets, un secret Docker ou une variable d’environnement sécurisée.
- La clé de chiffrement n’est jamais écrite dans `settings.json`. Sa perte rend les secrets chiffrés irrécupérables.
- Les secrets ne sont jamais renvoyés par l’API publique ni affichés dans l’interface utilisateur.
- Les fichiers `data/settings.json`, `data/admin_auth.json`, `data/.settings.key`, `.env` et les logs sont exclus de Git ou du contexte de construction Docker.

### Authentification administrateur

- L’administrateur peut modifier son mot de passe après connexion depuis `/admin`.
- Le nouveau mot de passe doit contenir au moins 12 caractères.
- Seul un hash `scrypt` salé est conservé dans `data/admin_auth.json`; le mot de passe n’est jamais stocké en clair.
- Le mot de passe actuel est exigé avant toute modification.
- Toutes les sessions administratives existantes sont invalidées après un changement de mot de passe.
- Après cinq connexions échouées depuis une même adresse, les nouvelles tentatives sont bloquées pendant 15 minutes.
- En production Docker, `ADMIN_PASSWORD_HASH` et `SECRET_KEY` doivent être définis dans `.env`; les valeurs par défaut de développement ne doivent pas être utilisées.

### Sessions et requêtes administratives

- Toutes les requêtes administratives modifiant des données sont protégées par un jeton CSRF aléatoire lié à la session.
- La connexion et la déconnexion administrateur sont également protégées contre les requêtes intersites.
- Les cookies de session utilisent `HttpOnly` et `SameSite=Strict`.
- Avec un déploiement HTTPS, définir `SESSION_COOKIE_SECURE=true` pour empêcher l’envoi du cookie sur une connexion HTTP.
- La déconnexion et le changement de mot de passe effacent la session courante.

### Contenu importé et aperçu

- Le HTML provenant des documents et des réponses IA est nettoyé avant la prévisualisation et l’import BookStack.
- Les balises actives ou dangereuses, notamment `script`, `iframe`, `object`, `embed` et les formulaires, sont supprimées.
- Les attributs événementiels comme `onclick` et `onerror`, ainsi que les URL `javascript:` et `vbscript:`, sont supprimés.
- Les archives ZIP sont lues sans extraction directe sur le disque, ce qui limite les risques de traversée de chemins.
- Les ZIP chiffrés, illisibles, contenant plus de 2 000 documents ou dépassant la limite décompressée sont refusés.

### Sécurité HTTP et réseau

- Tous les appels BookStack et IA passent côté serveur par un client HTTP centralisé; les tokens ne transitent pas par le navigateur.
- La vérification TLS est globale et activée par défaut. Sa désactivation doit être réservée aux certificats internes ou auto-signés sur un réseau maîtrisé.
- Les URL HTTP sont acceptées mais transmettent les données sans chiffrement; HTTPS reste obligatoire sur un réseau non fiable.
- Les réponses ajoutent notamment `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy` et une politique CSP.
- HSTS est envoyé automatiquement lorsque l’application est elle-même servie en HTTPS.
- Waitress remplace le serveur Flask de développement pour l’exécution de production.

### Journalisation

- Les logs détaillés n’enregistrent pas les tokens, clés API ou en-têtes d’autorisation.
- Les fichiers de logs sont rotatifs, limités en taille et exclus de Git ainsi que de l’image Docker.
- Le mode détaillé peut néanmoins contenir des noms de fichiers, modèles, endpoints et informations techniques; l’accès au répertoire `logs/` doit donc rester restreint.

### Recommandations de déploiement

1. Utiliser un reverse proxy HTTPS devant Waitress.
2. Définir `SECRET_KEY`, `ADMIN_PASSWORD_HASH` et `SETTINGS_ENCRYPTION_KEY` avec des valeurs uniques et fortes.
3. Activer `SESSION_COOKIE_SECURE=true` lorsque HTTPS est opérationnel.
4. Sauvegarder séparément `data/settings.json`, `data/admin_auth.json` et la clé de chiffrement.
5. Restreindre les permissions des répertoires `data/` et `logs/` au compte exécutant l’application.
6. Conserver la vérification TLS activée et renouveler régulièrement les tokens BookStack et les clés IA.
7. Ne jamais publier `.env`, `data/`, `logs/` ou une image Docker construite avant l’ajout du fichier `.dockerignore`.

## Notes

Le cache de prévisualisation est en mémoire et disparaît au redémarrage. Les dessins vectoriels PDF sont détectés mais ne sont pas rasterisés séparément afin d’éviter de transformer bordures et tableaux en images.
