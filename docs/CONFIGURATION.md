# Guide de configuration StackBridge

Ce document décrit les fonctions principales ajoutées à StackBridge et leur configuration.

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
7. cliquer sur **Tester la configuration OIDC** ;
8. activer OIDC puis enregistrer la configuration.

StackBridge utilise la découverte OIDC via :

```text
<issuer>/.well-known/openid-configuration
```

Le flux de connexion utilise Authorization Code avec PKCE S256.

### Configuration du client Keycloak

Créez un client OIDC dédié à StackBridge. La Redirect URI doit correspondre exactement à l'URL publique de StackBridge :

```text
https://stackbridge.exemple.fr/auth/oidc/callback
```

L'URL réellement générée dépend de l'adresse par laquelle le navigateur accède à StackBridge. En production, utilisez HTTPS et configurez correctement le reverse proxy.

Les claims `sub`, `name`/`preferred_username` et `email` sont utilisés pour identifier et afficher l'utilisateur. `sub` est l'identifiant OIDC stable de référence.

### OIDC StackBridge et OIDC BookStack

StackBridge et BookStack peuvent être déclarés comme deux clients du même Keycloak. L'utilisateur bénéficie alors du SSO du fournisseur d'identité.

Le token OIDC Keycloak ne remplace cependant pas le Token ID/Token Secret de l'API BookStack. Pour une attribution BookStack exacte des imports, utilisez le token API personnel de l'utilisateur.

## 5. Fallback local

L'option **fallback local** évite de bloquer l'accès à StackBridge si Keycloak/OIDC est indisponible ou mal configuré.

Lorsqu'elle est activée, la page de connexion propose **Continuer en mode local**. StackBridge crée alors une session locale de secours et journalise son utilisation.

Recommandation : conserver cette option activée au moins pendant la phase de déploiement OIDC. Dans un environnement exigeant une authentification centralisée stricte, elle peut ensuite être désactivée depuis Administration.

## 6. Import et glisser-déposer

L'importateur accepte plusieurs fichiers DOCX, PDF, Markdown, HTML et TXT ainsi que les ZIP.

Les fichiers peuvent être sélectionnés ou glissés-déposés. Une zone verte avec une coche et le nombre de fichiers confirme visuellement que la sélection a été prise en compte.

Pour conserver une arborescence complète de dossiers, créez une archive ZIP : les chemins internes peuvent être convertis en chapitres BookStack.

## 7. Moteur PDF/OCR V2

Le moteur PDF analyse chaque page :

- les pages numériques exploitables utilisent l'extraction native PyMuPDF ;
- les pages scannées ou dont le texte est insuffisant passent par Tesseract OCR ;
- l'image originale de la page est conservée comme solution de repli afin d'éviter qu'une page scannée disparaisse lorsque l'OCR échoue.

L'OCR effectue un prétraitement d'image puis plusieurs stratégies Tesseract afin de conserver le résultat le plus exploitable.

## 8. Amélioration IA

L'IA reste optionnelle et la version originale du document reste disponible.

Dans Administration, configurez l'URL du service IA, la clé éventuelle et le modèle. Les API compatibles OpenAI sont supportées, ainsi qu'un format JSON personnalisé et un preset Ollama.

Pour les gros documents, StackBridge découpe le contenu en blocs en essayant de préserver les éléments logiques : titres, tableaux, listes et blocs de code. Les documents peuvent être améliorés un par un ou avec **Améliorer tous les fichiers**, qui les traite séquentiellement.

Le sélecteur **Version pour tous** permet ensuite de choisir Originale ou Version IA pour l'ensemble des documents lorsque toutes les versions IA sont disponibles.

Par défaut, les images Base64 sont masquées avant l'appel IA puis restaurées après traitement afin d'éviter une consommation excessive du contexte. `AI_MAX_INPUT_TOKENS` vaut 6000 par défaut.

## 9. Secrets et sécurité

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

## 10. Diagnostic

Administration permet d'activer la journalisation détaillée et de consulter/télécharger les dernières lignes de `logs/app.log`.

Les logs permettent notamment de suivre les conversions, OCR, appels IA, connexions OIDC, utilisation du fallback et imports. Les secrets ne doivent pas être journalisés.
