# Description du problème

## Contexte

En Côte d'Ivoire et plus largement en Afrique de l'Ouest, WhatsApp est le principal canal de
vente pour un très grand nombre de petits commerçants (mode, chaussures, cosmétiques,
téléphones, accessoires). Le parcours d'achat se déroule presque entièrement dans la
conversation : photo du produit, questions du client, négociation, prise de commande, livraison.

## Douleurs observées

- Le vendeur répond manuellement à des dizaines de messages similaires par jour
  ("c'est combien ?", "vous avez en taille 42 ?", "vous livrez à Yopougon ?").
- Les réponses sont lentes en dehors des heures d'ouverture → clients perdus.
- Le stock réel n'est pas toujours reflété dans les réponses données (erreurs, survente).
- Aucune trace structurée des commandes : le suivi se fait "à la main" dans la tête du vendeur
  ou dans un cahier.

## Objectif du produit

Fournir un assistant conversationnel qui :

1. Répond immédiatement aux questions fréquentes (produit, prix, taille, couleur, livraison)
   en s'appuyant uniquement sur les données réelles du catalogue (pas d'invention de prix
   ou de disponibilité).
2. Utilise des outils (function calling) pour vérifier le stock, consulter l'historique
   client, et créer une commande dans une base structurée.
3. Reste disponible 24/7, avec une réponse dans le ton d'un vendeur humain ivoirien.
4. Donne au vendeur une vue de suivi (dashboard) sur les échanges, les produits les plus
   demandés, et la qualité perçue des réponses.

## Public cible

Petits vendeurs en ligne (1 à quelques employés) opérant principalement via WhatsApp, avec
un catalogue de quelques centaines de références et des zones de livraison limitées à
quelques villes/quartiers.

## Non-objectifs (hors périmètre pour cette version)

- Paiement en ligne intégré (mobile money) — commandes créées en statut "en attente".
- Génération/édition d'images produits.
- Support multi-vendeurs avec authentification avancée (un seul vendeur de démonstration).
