# StackBridge

**Document Import Studio for BookStack** â€” version `1.0.0`.

Import massif de documents DOCX, PDF, Markdown, HTML et TXT vers BookStack, avec structure dossiers â†’ chapitres, OCR Tesseract, prÃ©visualisation et amÃ©lioration IA optionnelle.

Lâ€™interface nâ€™utilise pas la sÃ©lection native de dossier du navigateur. Pour conserver une arborescence sans confirmation Chrome, compressez le dossier en ZIP puis sÃ©lectionnez lâ€™archive. Les chemins internes du ZIP deviennent les chapitres BookStack.

## Installation avec Docker

### PrÃ©requis

- Docker Engine ou Docker Desktop avec Compose v2 ;
- Git pour rÃ©cupÃ©rer et mettre Ã  jour le projet ;
- port TCP `5050` disponible.

### PremiÃ¨re installation

```bash
git clone https://github.com/odi2050/stackbridge.git
cd stackbridge
docker build --build-arg APP_VERSION=1.0.0 -t stackbridge:1.0.0 .
```

GÃ©nÃ©rez ensuite le fichier `.env` de maniÃ¨re interactive. La commande demande le mot de passe administrateur et crÃ©e automatiquement son hash scrypt ainsi que les clÃ©s de session et de chiffrement :

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

DÃ©marrez enfin StackBridge :

```bash
docker compose up -d --build
docker compose ps
```

Ouvrez `http://ADRESSE_DU_SERVEUR:5050`. Lâ€™administration est disponible dans `/admin`.

Le conteneur utilise Waitress avec huit threads. Les rÃ©glages chiffrÃ©s sont persistÃ©s dans `data/` et les journaux dans `logs/`. Le healthcheck interroge `/api/health` toutes les 30 secondes.

### Mise Ã  jour Docker

```bash
git pull
python scripts/check_release.py
docker compose build --pull
docker compose up -d
```

Avant une mise Ã  jour majeure, sauvegardez `.env`, `data/` et `logs/`. Ne supprimez jamais `data/.settings.key` si `SETTINGS_ENCRYPTION_KEY` nâ€™est pas dÃ©fini dans `.env`.

### ArrÃªt et redÃ©marrage

```bash
docker compose stop
docker compose start
docker compose restart
```

Pour retirer uniquement le conteneur tout en conservant les donnÃ©es :

```bash
docker compose down
```

## Versioning et releases Docker

StackBridge suit [Semantic Versioning](https://semver.org/lang/fr/) sous la forme `MAJEURE.MINEURE.CORRECTIF` :

- `MAJEURE` : changement incompatible de configuration, dâ€™API ou de donnÃ©es ;
- `MINEURE` : nouvelle fonctionnalitÃ© rÃ©trocompatible ;
- `CORRECTIF` : correction rÃ©trocompatible.

Le fichier `VERSION` est la source de rÃ©fÃ©rence dans le dÃ©pÃ´t. La mÃªme valeur doit Ãªtre reportÃ©e dans `APP_VERSION` du fichier `.env` lors dâ€™une release. Elle est ensuite :

- intÃ©grÃ©e Ã  lâ€™image sous `STACKBRIDGE_VERSION` ;
- utilisÃ©e pour le tag `stackbridge:<version>` ;
- inscrite dans les labels OCI de lâ€™image ;
- affichÃ©e dans lâ€™interface ;
- exposÃ©e par `/api/version` et `/api/health` ;
- utilisÃ©e pour invalider proprement le cache CSS et JavaScript.

### CrÃ©er une release

1. Choisir la nouvelle version SemVer, par exemple `1.1.0`.
2. Modifier `VERSION` et `APP_VERSION` dans `.env` avec exactement la mÃªme valeur.
3. Ajouter les changements dans `CHANGELOG.md` sous une section datÃ©e.
4. Valider la cohÃ©rence : `python scripts/check_release.py`.
5. Construire lâ€™image : `docker compose build --pull`.
6. VÃ©rifier sa version : `docker compose run --rm stackbridge python -c "from version import APP_VERSION; print(APP_VERSION)"`.
7. DÃ©marrer la release : `docker compose up -d`.
8. ContrÃ´ler son Ã©tat : `docker compose ps` puis ouvrir `/api/health`.
9. Si le dÃ©pÃ´t est versionnÃ© avec Git, crÃ©er un tag annotÃ© correspondant : `git tag -a v1.1.0 -m "StackBridge 1.1.0"`.

Ne rÃ©utilisez jamais un mÃªme tag pour deux images diffÃ©rentes. Pour les tests intermÃ©diaires, utilisez des prÃ©versions SemVer telles que `1.1.0-rc.1`; rÃ©servez `latest` comme alias facultatif dâ€™une version stable dÃ©jÃ  taguÃ©e.

## Installation directe sans Docker

### PrÃ©requis

- Python 3.12 ou version compatible ;
- Git ;
- Tesseract OCR facultatif mais nÃ©cessaire pour les PDF scannÃ©s ;
- accÃ¨s rÃ©seau Ã  BookStack et, si utilisÃ©e, Ã  lâ€™API IA.

Sous Debian ou Ubuntu, Tesseract peut Ãªtre installÃ© avec :

```bash
sudo apt update
sudo apt install tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng
```

Sous Windows, installez Tesseract puis ajoutez son rÃ©pertoire au `PATH`.

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

StackBridge Ã©coute sur `0.0.0.0:5050` avec Waitress. Le fichier `.env` est chargÃ© automatiquement au dÃ©marrage.

### Mise Ã  jour directe

```bash
git pull
python -m pip install -r requirements.txt
python scripts/check_release.py
```

RedÃ©marrez ensuite le processus StackBridge ou le service systÃ¨me qui lâ€™exÃ©cute.

## Administration

Ouvrir `/admin` pour configurer BookStack, lâ€™IA, la vÃ©rification TLS et les logs dÃ©taillÃ©s. La dÃ©couverte des modÃ¨les interroge lâ€™endpoint OpenAI-compatible `/v1/models` et propose une recherche dans les rÃ©sultats.

- `VÃ©rifier les certificats SSL/TLS` sâ€™applique Ã  tous les appels BookStack et IA.
- Les URL `http://` sont acceptÃ©es. Elles ne chiffrent pas le trafic et sont dÃ©conseillÃ©es hors rÃ©seau de confiance.
- `Journalisation dÃ©taillÃ©e globale` trace les routes, conversions, OCR, appels HTTP, IA et imports.
- Les journaux rotatifs sont Ã©crits dans `logs/app.log` et consultables depuis lâ€™administration.

Avant un appel IA, les images Base64 sont remplacÃ©es par de petits marqueurs puis restaurÃ©es aprÃ¨s la rÃ©ponse. Cela Ã©vite de consommer le quota de tokens avec des donnÃ©es dâ€™image. `AI_MAX_INPUT_TOKENS` fixe la limite prÃ©ventive du texte envoyÃ© (6000 par dÃ©faut).

Lâ€™option administrative Â« Envoyer les images Ã  lâ€™IA Â» permet de dÃ©sactiver ce masquage. Elle est dÃ©sactivÃ©e par dÃ©faut, car lâ€™envoi des images Base64 peut dÃ©passer rapidement les limites de tokens du fournisseur.

### API IA personnalisÃ©e

Le mode personnalisÃ© de lâ€™administration permet de dÃ©finir lâ€™endpoint POST, le corps JSON et le chemin du texte dans la rÃ©ponse. Les variables disponibles sont `{{model}}`, `{{system_prompt}}`, `{{prompt}}`, `{{html}}` et `{{level}}`. Les chemins de rÃ©ponse utilisent une notation par points, par exemple `message.content` ou `choices.0.message.content`. Un prÃ©rÃ©glage Ollama est fourni dans lâ€™interface.

Les tokens et clÃ©s API ne sont jamais affichÃ©s dans lâ€™interface utilisateur. Ils sont conservÃ©s chiffrÃ©s dans `data/settings.json`, qui est exclu de Git.

Les champs sensibles de `settings.json` (`token_id`, `token_secret` et `ai_api_key`) sont chiffrÃ©s avec Fernet. Une clÃ© locale est crÃ©Ã©e dans `data/.settings.key`; en production, utilisez plutÃ´t `SETTINGS_ENCRYPTION_KEY` depuis un secret Docker ou une variable dâ€™environnement. Ne perdez pas cette clÃ©, sinon les valeurs deviennent irrÃ©cupÃ©rables.

Lâ€™administrateur peut changer son mot de passe depuis le panneau. Seul son hash scrypt est stockÃ© dans `data/admin_auth.json`.

## SÃ©curitÃ©

### Protection des secrets

- Le Token ID BookStack, le Token Secret et la clÃ© API IA sont chiffrÃ©s au repos avec Fernet dans `data/settings.json`.
- Les anciennes valeurs en clair sont migrÃ©es automatiquement au premier chargement.
- La clÃ© locale est enregistrÃ©e dans `data/.settings.key` avec des permissions restrictives lorsque le systÃ¨me les prend en charge.
- En production, il est recommandÃ© de fournir `SETTINGS_ENCRYPTION_KEY` depuis un gestionnaire de secrets, un secret Docker ou une variable dâ€™environnement sÃ©curisÃ©e.
- La clÃ© de chiffrement nâ€™est jamais Ã©crite dans `settings.json`. Sa perte rend les secrets chiffrÃ©s irrÃ©cupÃ©rables.
- Les secrets ne sont jamais renvoyÃ©s par lâ€™API publique ni affichÃ©s dans lâ€™interface utilisateur.
- Les fichiers `data/settings.json`, `data/admin_auth.json`, `data/.settings.key`, `.env` et les logs sont exclus de Git ou du contexte de construction Docker.

### Authentification administrateur

- Lâ€™administrateur peut modifier son mot de passe aprÃ¨s connexion depuis `/admin`.
- Le nouveau mot de passe doit contenir au moins 12 caractÃ¨res.
- Seul un hash `scrypt` salÃ© est conservÃ© dans `data/admin_auth.json`; le mot de passe nâ€™est jamais stockÃ© en clair.
- Le mot de passe actuel est exigÃ© avant toute modification.
- Toutes les sessions administratives existantes sont invalidÃ©es aprÃ¨s un changement de mot de passe.
- AprÃ¨s cinq connexions Ã©chouÃ©es depuis une mÃªme adresse, les nouvelles tentatives sont bloquÃ©es pendant 15 minutes.
- En production Docker, `ADMIN_PASSWORD_HASH` et `SECRET_KEY` doivent Ãªtre dÃ©finis dans `.env`; les valeurs par dÃ©faut de dÃ©veloppement ne doivent pas Ãªtre utilisÃ©es.

### Sessions et requÃªtes administratives

- Toutes les requÃªtes administratives modifiant des donnÃ©es sont protÃ©gÃ©es par un jeton CSRF alÃ©atoire liÃ© Ã  la session.
- La connexion et la dÃ©connexion administrateur sont Ã©galement protÃ©gÃ©es contre les requÃªtes intersites.
- Les cookies de session utilisent `HttpOnly` et `SameSite=Strict`.
- Avec un dÃ©ploiement HTTPS, dÃ©finir `SESSION_COOKIE_SECURE=true` pour empÃªcher lâ€™envoi du cookie sur une connexion HTTP.
- La dÃ©connexion et le changement de mot de passe effacent la session courante.

### Contenu importÃ© et aperÃ§u

- Le HTML provenant des documents et des rÃ©ponses IA est nettoyÃ© avant la prÃ©visualisation et lâ€™import BookStack.
- Les balises actives ou dangereuses, notamment `script`, `iframe`, `object`, `embed` et les formulaires, sont supprimÃ©es.
- Les attributs Ã©vÃ©nementiels comme `onclick` et `onerror`, ainsi que les URL `javascript:` et `vbscript:`, sont supprimÃ©s.
- Les archives ZIP sont lues sans extraction directe sur le disque, ce qui limite les risques de traversÃ©e de chemins.
- Les ZIP chiffrÃ©s, illisibles, contenant plus de 2 000 documents ou dÃ©passant la limite dÃ©compressÃ©e sont refusÃ©s.

### SÃ©curitÃ© HTTP et rÃ©seau

- Tous les appels BookStack et IA passent cÃ´tÃ© serveur par un client HTTP centralisÃ©; les tokens ne transitent pas par le navigateur.
- La vÃ©rification TLS est globale et activÃ©e par dÃ©faut. Sa dÃ©sactivation doit Ãªtre rÃ©servÃ©e aux certificats internes ou auto-signÃ©s sur un rÃ©seau maÃ®trisÃ©.
- Les URL HTTP sont acceptÃ©es mais transmettent les donnÃ©es sans chiffrement; HTTPS reste obligatoire sur un rÃ©seau non fiable.
- Les rÃ©ponses ajoutent notamment `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy` et une politique CSP.
- HSTS est envoyÃ© automatiquement lorsque lâ€™application est elle-mÃªme servie en HTTPS.
- Waitress remplace le serveur Flask de dÃ©veloppement pour lâ€™exÃ©cution de production.

### Journalisation

- Les logs dÃ©taillÃ©s nâ€™enregistrent pas les tokens, clÃ©s API ou en-tÃªtes dâ€™autorisation.
- Les fichiers de logs sont rotatifs, limitÃ©s en taille et exclus de Git ainsi que de lâ€™image Docker.
- Le mode dÃ©taillÃ© peut nÃ©anmoins contenir des noms de fichiers, modÃ¨les, endpoints et informations techniques; lâ€™accÃ¨s au rÃ©pertoire `logs/` doit donc rester restreint.

### Recommandations de dÃ©ploiement

1. Utiliser un reverse proxy HTTPS devant Waitress.
2. DÃ©finir `SECRET_KEY`, `ADMIN_PASSWORD_HASH` et `SETTINGS_ENCRYPTION_KEY` avec des valeurs uniques et fortes.
3. Activer `SESSION_COOKIE_SECURE=true` lorsque HTTPS est opÃ©rationnel.
4. Sauvegarder sÃ©parÃ©ment `data/settings.json`, `data/admin_auth.json` et la clÃ© de chiffrement.
5. Restreindre les permissions des rÃ©pertoires `data/` et `logs/` au compte exÃ©cutant lâ€™application.
6. Conserver la vÃ©rification TLS activÃ©e et renouveler rÃ©guliÃ¨rement les tokens BookStack et les clÃ©s IA.
7. Ne jamais publier `.env`, `data/`, `logs/` ou une image Docker construite avant lâ€™ajout du fichier `.dockerignore`.

## Notes

Le cache de prÃ©visualisation est en mÃ©moire et disparaÃ®t au redÃ©marrage. Les dessins vectoriels PDF sont dÃ©tectÃ©s mais ne sont pas rasterisÃ©s sÃ©parÃ©ment afin dâ€™Ã©viter de transformer bordures et tableaux en images.

