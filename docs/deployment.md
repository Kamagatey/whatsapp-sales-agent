# Préparation au déploiement cloud (bonus)

Ce projet est conçu pour tourner en local via `docker compose`, mais est prêt pour un
déploiement cloud avec des changements minimes :

## Option A — VM unique (le plus simple)

1. Provisionner une VM (ex. DigitalOcean Droplet, OVH, AWS Lightsail — pertinent pour
   un projet ivoirien/francophone).
2. Installer Docker + docker-compose.
3. Cloner le repo, renseigner `.env` avec la clé OpenAI.
4. `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`
   (le fichier `docker-compose.prod.yml`, à créer, retire les volumes de dev et ajoute
   un reverse proxy Caddy/Traefik avec HTTPS automatique).

## Option B — Services managés

- **API (FastAPI)** → conteneur sur un service type Render / Railway / AWS App Runner.
- **PostgreSQL + pgvector** → base managée (ex. Supabase, Neon avec extension pgvector,
  ou RDS Postgres avec l'extension activée).
- **Grafana** → Grafana Cloud (tier gratuit) au lieu du conteneur local.
- **Streamlit** → Streamlit Community Cloud, pointant vers l'API déployée via
  `API_BASE_URL`.

## Variables à externaliser en production

- `OPENAI_API_KEY` en secret manager (jamais dans l'image).
- `DATABASE_URL` complet plutôt que des variables séparées.
- `CORS_ORIGINS` restreint au domaine du front.

## Webhook WhatsApp réel (prochaine étape)

`app/api/whatsapp_webhook.py` contient un stub de endpoint compatible avec le format
Meta Cloud API. Pour une intégration réelle il faudrait :
1. Un numéro WhatsApp Business vérifié.
2. Un endpoint HTTPS public pour recevoir les webhooks entrants.
3. Remplacer l'appel direct à l'agent (actuellement via `/chat`) par un appel depuis
   le webhook, avec envoi de la réponse via l'API Graph de Meta.
