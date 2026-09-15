# Changelog

Toutes les modifications importantes de StackBridge sont documentées ici. Le projet suit [Semantic Versioning](https://semver.org/lang/fr/) et le format [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).

## [1.1.0] - 2026-09-15

### Ajouté

- Support officiel d'un déploiement derrière reverse proxy avec préfixe d'URL, par exemple `/import-document`.
- Prise en charge des en-têtes `X-Forwarded-*` via `ProxyFix`, activable avec `TRUST_PROXY_HEADERS=true`.
- Génération correcte des URL OIDC publiques et de la Redirect URI derrière HTTPS/reverse proxy.
- Support des autorités de certification internes montées dans `./certs` et ajoutées au trust store du conteneur.
- Utilisation cohérente du bundle CA pour la découverte OIDC, l'échange du code contre un token et l'appel `userinfo`.

### Corrigé

- Liens HTML, ressources statiques et appels API JavaScript qui supposaient auparavant un déploiement à la racine `/`.
- Redirection après authentification OIDC ou fallback local afin de conserver le préfixe public.
- Test OIDC de l'administration afin qu'il utilise immédiatement l'état de la vérification TLS affiché dans l'interface.

### Sécurité

- Les certificats locaux placés dans `certs/` sont ignorés par Git et par le contexte de build Docker afin d'éviter leur inclusion accidentelle dans l'image.
- `verify_tls` reste activé par défaut ; les PKI internes doivent être ajoutées au magasin de confiance plutôt que contournées avec `verify=False`.

## [1.0.0] - 2026-08-31

### Ajouté

- Import DOCX, PDF, Markdown, HTML, TXT et ZIP vers BookStack.
- Structure ZIP vers chapitres, OCR Tesseract et prévisualisation.
- Amélioration IA OpenAI-compatible et requêtes JSON personnalisées.
- Administration persistante, découverte des modèles et diagnostic détaillé.
- Chiffrement des secrets, mot de passe administrateur modifiable, CSRF et nettoyage HTML.
- Interface responsive, notifications intégrées et suivi de progression.
- Exécution de production avec Waitress et Docker.
