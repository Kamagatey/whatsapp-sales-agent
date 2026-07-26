# Intégration WhatsApp réelle — options et choix retenu

Le projet expose déjà un agent complet derrière `/chat` (FastAPI). Pour le connecter à un
vrai numéro WhatsApp, plusieurs approches existent. Comparatif :

| Option | Officiel ? | Coût | Effort de mise en place | Risque | Adapté à |
|---|---|---|---|---|---|
| **Meta WhatsApp Cloud API** (retenu) | ✅ Oui | Gratuit en mode test (jusqu'à 5 numéros destinataires vérifiés) ; conversations de service gratuites en prod | Moyen (compte Meta for Developers + webhook HTTPS) | Aucun (usage conforme aux CGU) | Démo de certification, puis passage en prod sans tout réécrire |
| **Twilio WhatsApp Sandbox** | ✅ Oui (via BSP) | Sandbox gratuit, prod payante | Faible (setup en quelques minutes) | Aucun | Prototypage très rapide, si tu ne veux pas gérer Meta directement |
| **Baileys / whatsapp-web.js / Evolution API** | ❌ Non officiel (protocole web WhatsApp) | Gratuit (auto-hébergé) | Faible à moyen (scan d'un QR code, pas de vérification Meta) | Risque de bannissement du numéro (CGU WhatsApp) | Tests personnels rapides, pas recommandé pour un vrai vendeur |
| **OpenClaw** (mentionné par l'utilisateur) | Dépend du mode choisi (Business API ou pont non-officiel) | Variable selon hébergement | Élevé si on veut y brancher NOTRE agent personnalisé | Dépend du mode choisi | Plutôt pour héberger un agent générique "prêt à l'emploi" ; ici on a déjà un pipeline RAG + tools sur mesure, donc OpenClaw ajouterait une couche d'indirection sans bénéfice net |

## Choix retenu : Meta WhatsApp Cloud API

C'est l'option la plus pertinente ici car :
- Le webhook `app/api/whatsapp_webhook.py` est déjà implémenté et branché sur `SalesAgent`.
- Le numéro de test Meta est gratuit et suffit largement pour la démonstration du projet
  (certification, jury, démo à un vendeur pilote).
- Contrairement à Baileys/whatsapp-web.js, il n'y a aucun risque de bannissement.
- Migration vers un vrai numéro business = changer les variables d'environnement, pas le code.

### Mise en place (numéro de test gratuit)

1. Créer un compte sur [developers.facebook.com](https://developers.facebook.com), créer une
   app de type "Business", ajouter le produit **WhatsApp**.
2. Meta fournit un numéro de test + un `Temporary access token` (valable 24h — générer un
   token permanent via un **System User** pour un usage plus long).
3. Récupérer `Phone Number ID` (visible dans la config WhatsApp de l'app).
4. Renseigner dans `.env` :
   ```
   WHATSAPP_ACCESS_TOKEN=EAAG...
   WHATSAPP_PHONE_NUMBER_ID=123456789012345
   WHATSAPP_VERIFY_TOKEN=un-secret-que-tu-choisis
   ```
5. Exposer l'API en HTTPS. En développement, le plus simple est `ngrok` :
   ```
   ngrok http 8000
   ```
   Copier l'URL HTTPS générée.
6. Dans la config webhook de l'app Meta : callback URL =
   `https://<url-ngrok>/whatsapp/webhook`, verify token = celui mis dans `.env`.
   S'abonner au champ `messages`.
7. Ajouter ton propre numéro comme destinataire de test (dans la section "To" de la config
   WhatsApp, max 5 numéros en mode test).
8. Envoie un message WhatsApp au numéro de test → il doit passer par `SalesAgent` et
   recevoir une réponse.

### Limites du mode test

- 5 numéros destinataires maximum, ajoutés manuellement.
- Token temporaire à régénérer toutes les 24h (sauf token System User permanent).
- Pas de "green tick" ni de nom affiché personnalisé sans vérification business complète —
  non nécessaire pour la démo.

### Passage en production (hors périmètre immédiat)

Voir `docs/deployment.md`. Il faudra : vérification business Meta, un numéro dédié, et
un token permanent stocké en secret manager plutôt qu'en `.env`.

## Pourquoi pas OpenClaw dans ce projet

OpenClaw (et les outils similaires type Clawbase) sont conçus pour donner à **un agent
générique** un canal WhatsApp "clé en main", en installant des *skills* dans leur propre
écosystème. Ici, le projet a volontairement construit son propre pipeline (RAG hybride,
tools métier, monitoring, évaluation) pour répondre à la grille LLM Zoomcamp — faire
transiter cet agent par une couche d'orchestration tierce ajouterait de la complexité et
une dépendance externe sans réel gain, puisque le besoin (recevoir un message, appeler
l'agent, renvoyer la réponse) est déjà couvert par un simple webhook Meta. OpenClaw
redeviendrait pertinent si, à terme, on voulait exposer le même agent sur plusieurs canaux
(Telegram, Slack, Discord) sans dupliquer le code de webhook pour chacun.
