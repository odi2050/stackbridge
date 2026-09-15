# Guide de configuration StackBridge

Ce document décrit les fonctions principales de StackBridge et leur configuration, y compris OIDC, le déploiement derrière reverse proxy et l'utilisation d'une PKI interne.

## 1. Fonctionnement général

StackBridge convertit des documents DOCX, PDF, Markdown, HTML et TXT avant de les importer dans BookStack. Les archives ZIP peuvent conserver une arborescence de dossiers qui devient une structure de chapitres BookStack.

Le flux conseillé est :

1. choisir l'identité BookStack utilisée pour l'import ;
2. charger le livre de destination ;
3. déposer ou sélectionner les documents ;
4. analyser les documents ;
5. contrôler la prévisualisation ;
6. appliquer éventuellement l'amélioration IA ;
7. importer les pages sélectionnées.

## 2. Connexion BookStack administrateur

Dans **Administration > Connexion BookStack**, renseignez :

- **URL BookStack** : URL de l'instance, par exemple `https://bookstack.exemple.fr` ;
- **Token ID** : token API du compte utilisé par défaut ;
- **Token Secret** : secret associé.

Cette connexion est utilisée par défaut pour tous les utilisateurs qui ne fournissent pas leur propre token.

Le compte BookStack associé au token doit avoir les permissions nécessaires pour consulter les livres et créer les chapitres/pages voulus.

## 3. Token BookStack personnel et traçabilité

Dans l'importateur, l'utilisateur peut activer **Utiliser mon token API BookStack personnel**.

Dans BookStack :

1. se connecter avec son compte personnel ;
2. ouvrir **Mon compte / My Account** ;
3. ouvrir **Accès et sécurité / Access & Security** ;
4. créer un token dans **API Tokens**, par exemple `StackBridge` ;
5. choisir une expiration adaptée ;
6. copier immédiatement le **Token ID** et le **Token Secret** ;
7. saisir ces deux valeurs dans StackBridge puis cliquer sur **Charger les livres**.

BookStack n'affiche le secret qu'à la création. Si la section API Tokens n'est pas visible, le rôle de l'utilisateur doit recevoir la permission **Access System API**.

Les appels API BookStack héritent des permissions de l'utilisateur propriétaire du token. L'utilisation d'un token personnel permet donc à BookStack d'attribuer les créations au compte correspondant.

Les identifiants personnels saisis dans l'importateur ne remplacent pas la configuration administrateur enregistrée.

## 4. OIDC / Keycloak

OIDC est facultatif. Sans OIDC, StackBridge fonctionne comme auparavant.

Dans **Administration > Authentification OIDC / Keycloak** :

1. renseigner l'**Issuer URL**, par exemple `https://keycloak.exemple.fr/realms/entreprise` ;
2. renseigner le **Client ID** créé pour StackBridge ;
3. renseigner le **Client Secret** si le client Keycloak est confidentiel ;
4. conserver généralement les scopes `openid profile email` ;
5. choisir le nom affiché, par exemple `SSO entreprise` ;
6. laisser **fallback local** activé pendant la mise en service ;
7. laisser **Vérifier les certificats SSL/TLS** activé ;
8. cliquer sur **Tester la configuration OIDC** ;
9. activer OIDC puis enregistrer la configuration.

StackBridge utilise la découverte OIDC via :

```text
<issuer>/.well-known/openid-configuration
```

Le flux de connexion utilise Authorization Code avec PKCE S256.

### Configuration du client Keycloak

Créez un client OIDC dédié à StackBridge. Pour une installation à la racine, la Redirect URI est par exemple :

```text
https://stackbridge.exemple.fr/auth/oidc/callback
```

Si StackBridge est publié sous `/import-document`, elle devient :

```text
https://bookstack.exemple.fr/import-document/auth/oidc/callback
```

L'URI exacte est affichée dans **Administration > Authentification OIDC / Keycloak**. Utilisez cette valeur dans Keycloak.

Les claims `sub`, `name`/`preferred_username` et `email` sont utilisés pour identifier et afficher l'utilisateur. `sub` est l'identifiant OIDC stable de référence.

### OIDC StackBridge et OIDC BookStack

StackBridge et BookStack peuvent être déclarés comme deux clients du même Keycloak. L'utilisateur bénéficie alors du SSO du fournisseur d'identité.

Le token OIDC Keycloak ne remplace cependant pas le Token ID/Token Secret de l'API BookStack. Pour une attribution BookStack exacte des imports, utilisez le token API personnel de l'utilisateur.

## 5. Reverse proxy et sous-chemin `/import-document`

StackBridge peut être publié sous un préfixe d'URL, par exemple :

```text
https://bookstack.exemple.fr/import-document/
```

Le reverse proxy retire le préfixe avant d'envoyer la requête au conteneur puis indique à StackBridge son URL publique avec `X-Forwarded-Prefix`.

Dans `.env`, activez la confiance envers les en-têtes du reverse proxy :

```env
SESSION_COOKIE_SECURE=true
TRUST_PROXY_HEADERS=true
```

`TRUST_PROXY_HEADERS=true` ne doit être utilisé que si StackBridge reçoit les requêtes depuis un reverse proxy de confiance. Si le port `5050` reste exposé sur le réseau, protégez-le avec un pare-feu ou limitez son écoute au proxy.

### Exemple Apache HTTP Server

Modules nécessaires : `proxy`, `proxy_http`, `headers` et SSL si Apache termine HTTPS.

Exemple :

```apache
ProxyPreserveHost On

ProxyPass        /import-document/ http://127.0.0.1:5050/
ProxyPassReverse /import-document/ http://127.0.0.1:5050/

<Location /import-document/>
    RequestHeader set X-Forwarded-Proto "https"
    RequestHeader set X-Forwarded-Prefix "/import-document"
</Location>
```

Apache ajoute normalement les en-têtes `X-Forwarded-For` et `X-Forwarded-Host` en mode reverse proxy. `X-Forwarded-Proto` et `X-Forwarded-Prefix` sont définis explicitement ici.

Si le même VirtualHost contient d'autres règles `ProxyPass`, placez la règle la plus spécifique `/import-document/` avant une éventuelle règle générique `/`.

Une fois cette configuration active, les ressources statiques, appels `/api`, pages d'administration et routes OIDC restent automatiquement sous `/import-document`.

## 6. PKI interne et certificats locaux

Si Keycloak, BookStack ou un autre service HTTPS utilise un certificat signé par une AC interne, ne désactivez pas la vérification TLS. Ajoutez l'AC racine et les éventuelles AC intermédiaires au magasin de confiance du conteneur.

Créez sur l'hôte :

```text
stackbridge/
└── certs/
    ├── root-ca.crt
    └── intermediate-ca.crt
```

Chaque fichier doit contenir un certificat CA au format PEM avec l'extension `.crt`. Ne placez jamais de clé privée dans ce dossier.

Le `docker-compose.yml` monte automatiquement :

```text
./certs -> /usr/local/share/ca-certificates/stackbridge
```

Au démarrage, StackBridge lance `update-ca-certificates` lorsque des fichiers `.crt` sont présents. Le bundle système `/etc/ssl/certs/ca-certificates.crt` est ensuite utilisé par `requests` et Authlib.

Redémarrez après ajout ou remplacement d'un certificat :

```bash
docker compose up -d --force-recreate
```

Pour vérifier depuis le conteneur :

```bash
docker exec stackbridge python -c "import requests; print(requests.get('https://keycloak.exemple.fr', timeout=10).status_code)"
```

Dans l'administration StackBridge, laissez **Vérifier les certificats SSL/TLS** activé.

Le certificat présenté par Keycloak doit aussi contenir le nom DNS utilisé dans l'Issuer URL dans son SAN.

Le dossier `certs/` est exclu de Git et du contexte de build Docker afin d'éviter l'inclusion accidentelle de certificats internes dans le dépôt ou dans l'image publique.

## 7. Fallback local

L'option **fallback local** évite de bloquer l'accès à StackBridge si Keycloak/OIDC est indisponible ou mal configuré.

Lorsqu'elle est activée, la page de connexion propose **Continuer en mode local**. StackBridge crée alors une session locale de secours et journalise son utilisation.

Recommandation : conserver cette option activée au moins pendant la phase de déploiement OIDC. Dans un environnement exigeant une authentification centralisée stricte, elle peut ensuite être désactivée depuis Administration.

## 8. Import et glisser-déposer

L'importateur accepte plusieurs fichiers DOCX, PDF, Markdown, HTML et TXT ainsi que les ZIP.

Les fichiers peuvent être sélectionnés ou glissés-déposés. Une zone verte avec une coche et le nombre de fichiers confirme visuellement que la sélection a été prise en compte.

Pour conserver une arborescence complète de dossiers, créez une archive ZIP : les chemins internes peuvent être convertis en chapitres BookStack.

## 9. Moteur PDF/OCR V2

Le moteur PDF analyse chaque page :

- les pages numériques exploitables utilisent l'extraction native PyMuPDF ;
- les pages scannées ou dont le texte est insuffisant passent par Tesseract OCR ;
- l'image originale de la page est conservée comme solution de repli afin d'éviter qu'une page scannée disparaisse lorsque l'OCR échoue.

L'OCR effectue un prétraitement d'image puis plusieurs stratégies Tesseract afin de conserver le résultat le plus exploitable.

## 10. Amélioration IA

L'IA reste optionnelle et la version originale du document reste disponible.

Dans Administration, configurez l'URL du service IA, la clé éventuelle et le modèle. Les API compatibles OpenAI sont supportées, ainsi qu'un format JSON personnalisé et un preset Ollama.

Pour les gros documents, StackBridge découpe le contenu en blocs en essayant de préserver les éléments logiques : titres, tableaux, listes et blocs de code. Les documents peuvent être améliorés un par un ou avec **Améliorer tous les fichiers**, qui les traite séquentiellement.

Le sélecteur **Version pour tous** permet ensuite de choisir Originale ou Version IA pour l'ensemble des documents lorsque toutes les versions IA sont disponibles.

Par défaut, les images Base64 sont masquées avant l'appel IA puis restaurées après traitement afin d'éviter une consommation excessive du contexte. `AI_MAX_INPUT_TOKENS` vaut 3000 par défaut dans l'image Docker.

## 11. Secrets et sécurité

Les secrets administrateur sont stockés chiffrés avec Fernet dans `data/settings.json`. Cela comprend notamment les tokens BookStack, la clé IA et le Client Secret OIDC.

Conservez impérativement :

- `.env` ;
- `data/settings.json` ;
- `data/admin_auth.json` ;
- `data/.settings.key` si `SETTINGS_ENCRYPTION_KEY` n'est pas fourni par l'environnement.

Avec HTTPS, définissez :

```env
SESSION_COOKIE_SECURE=true
```

N'activez `TRUST_PROXY_HEADERS=true` que lorsque les connexions directes au backend sont contrôlées et que les en-têtes `X-Forwarded-*` proviennent du reverse proxy attendu.

## 12. Diagnostic

Administration permet d'activer la journalisation détaillée et de consulter/télécharger les dernières lignes de `logs/app.log`.

Les logs permettent notamment de suivre les conversions, OCR, appels IA, connexions OIDC, utilisation du fallback et imports. Les secrets ne doivent pas être journalisés.
