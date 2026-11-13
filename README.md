# 🏡 Veille Immobilière Automatisée
### Rapport Quotidien par E-mail & Interface Web Hébergée sur Vercel (100% Gratuit)

Application complète, modulaire et **100 % gratuite** pour surveiller les annonces immobilières (maisons, appartements) à partir de vos critères et recevoir **chaque jour un rapport soigné par e-mail**, avec une **interface web moderne hébergée sur Vercel** accessible depuis votre smartphone ou PC.

---

## 🏛️ Architecture Hybride (Option A)

```
   ┌──────────────────────────────────────────────────────────────┐
   │             📱 Smartphone / PC (N'importe où)               │
   │               https://votre-veille-immo.vercel.app           │
   └──────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
   ┌──────────────────────────────────────────────────────────────┐
   │             ⚡ VERCEL (Interface Web Gratuite)              │
   │    - Gestion des recherches (Ajouter, Activer, Tester)       │
   │    - Bouton pour déclencher le rapport à la demande          │
   │    - Sauvegarde les modifications dans le dépôt GitHub       │
   └──────────────────────────────┬───────────────────────────────┘
                                  │ (Sync data/sites_config.json)
                                  ▼
   ┌──────────────────────────────────────────────────────────────┐
   │             🐙 GITHUB (Dépôt Git & GitHub Actions)           │
   │    - CRON : Exécution automatique tous les matins à 08h00    │
   │    - Scraping résilient des sites configurés                 │
   │    - Filtre anti-doublons (seen_announcements.json)          │
   └──────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
   ┌──────────────────────────────────────────────────────────────┐
   │             📧 Boîte E-mail (Rapport Quotidien HTML)         │
   │    - Liens des recherches + fiches complètes avec photos     │
   └──────────────────────────────────────────────────────────────┘
```

---

## 📋 Table des Matières

1. [Fonctionnalités Clés](#-fonctionnalités-clés)
2. [Étape 1 : Configuration E-mail (SMTP Gratuit)](#-étape-1--configuration-e-mail-smtp-gratuit)
3. [Étape 2 : Déploiement sur GitHub Actions (Moteur de Scraping)](#-étape-2--déploiement-sur-github-actions-moteur-de-scraping)
4. [Étape 3 : Déploiement de l'Interface sur Vercel (100% Gratuit)](#-étape-3--déploiement-de-linterface-sur-vercel-100-gratuit)
5. [Utilisation en Local](#-utilisation-en-local)
6. [Personnalisation des Portails](#-personnalisation-des-portails)

---

## 🚀 Fonctionnalités Clés

- 🌐 **Interface Web Déployée sur Vercel :** Ajoutez ou activez des recherches depuis votre téléphone où que vous soyez.
- 📧 **Rapport Quotidien par E-mail :** Envoyé automatiquement chaque matin à 08h00 via GitHub Actions.
- ⚡ **Déclenchement Manuel en 1 Clic :** Un bouton *"Lancer le rapport"* sur l'interface Vercel permet de forcer une analyse immédiate.
- 🧪 **Test de Scraping en Direct :** Visualisez instantanément les résultats d'un portail (photos, titres, prix) avant de l'enregistrer.
- 💾 **Anti-Doublons Garanti :** Mémorise les offres déjà envoyées dans `data/seen_announcements.json`.
- 💰 **100 % Gratuit :** Aucune carte bancaire requise, fonctionne entièrement sur les offres gratuites de Vercel et GitHub.

---

## 📧 Étape 1 : Configuration E-mail (SMTP Gratuit)

Vous pouvez utiliser Gmail ou n'importe quel fournisseur standard :

### Pour Gmail :
1. Rendez-vous sur votre compte Google : [Sécurité Google](https://myaccount.google.com/security).
2. Activez la **Validation en deux étapes**.
3. Allez sur [Mots de passe des applications](https://myaccount.google.com/apppasswords).
4. Créez un mot de passe nommé `Veille Immo` et notez le code de 16 lettres (ex: `abcd efgh ijkl mnop`).
5. Vos paramètres SMTP :
   - `SMTP_HOST` : `smtp.gmail.com`
   - `SMTP_PORT` : `587`
   - `SMTP_USER` : `votre.adresse@gmail.com`
   - `SMTP_PASSWORD` : votre mot de passe d'application de 16 lettres
   - `EMAIL_TO` : l'adresse de réception du rapport

---

## 🐙 Étape 2 : Déploiement sur GitHub Actions (Moteur de Scraping)

### 2.1 Pousser le projet sur GitHub
Créez un dépôt sur [GitHub](https://github.com/new) (privé ou public) :
```bash
git init
git add .
git commit -m "feat: veille immobilière complète"
git branch -M main
git remote add origin https://github.com/<VOTRE_PSEUDO>/<VOTRE_REPO>.git
git push -u origin main
```

### 2.2 Ajouter les Secrets sur GitHub
Dans votre dépôt GitHub : **Settings** > **Secrets and variables** > **Actions** > **New repository secret** :
- `SMTP_HOST` : `smtp.gmail.com`
- `SMTP_PORT` : `587`
- `SMTP_USER` : `votre.email@gmail.com`
- `SMTP_PASSWORD` : `votre_mot_de_passe_16_lettres`
- `EMAIL_TO` : `votre.email@gmail.com`

### 2.3 Activer les droits d'écriture GitHub Actions
1. Dans votre dépôt, allez dans **Settings** > **Actions** > **General**.
2. Dans **Workflow permissions**, cochez **"Read and write permissions"**.
3. Cliquez sur **Save**.

---

## ▲ Étape 3 : Déploiement de l'Interface sur Vercel (100% Gratuit)

Vercel va héberger votre interface d'administration avec un certificat SSL et une URL publique gratuite (ex: `https://votre-projet.vercel.app`).

### 3.1 Importer le projet sur Vercel
1. Rendez-vous sur [vercel.com](https://vercel.com) et connectez-vous avec votre compte GitHub.
2. Cliquez sur **"Add New..."** > **"Project"**.
3. Sélectionnez votre dépôt GitHub `veille-immo` et cliquez sur **Import**.
4. Laissez les paramètres de build par défaut (le fichier [`vercel.json`](file:///c:/dev/app/veille%20immo/vercel.json) est déjà configuré).

### 3.2 Ajouter les 2 variables d'environnement sur Vercel
Dans la section **Environment Variables** sur Vercel, ajoutez :
- **`GITHUB_REPO`** : `votre-pseudo/nom-du-repo` (ex: `jean/veille-immo`)
- **`GITHUB_TOKEN`** : Un Personal Access Token GitHub avec la permission `repo` (permet à l'interface Vercel de sauvegarder vos recherches dans le fichier `data/sites_config.json` et de déclencher les workflows à distance).  
  *(Pour le générer : sur GitHub > votre profil > **Settings** > **Developer Settings** > **Personal access tokens** > **Tokens (classic)** > cochez `repo` et `workflow`).*

5. Cliquez sur **Deploy**.

> 🎉 Votre interface est en ligne ! Vous pouvez l'ajouter à l'écran d'accueil de votre smartphone comme une application native.

---

## 💻 Utilisation en Local

Vous pouvez également lancer l'interface web en local sur votre machine sans rien déployer :

```bash
# Lancer l'interface web sur http://localhost:8080
py src/main.py --ui

# Tester le scraping en simulation (crée data/preview_daily_report.html)
py src/main.py --dry-run

# Tester l'envoi d'un e-mail
py src/main.py --test-email

# Lancer la suite de 18 tests unitaires
py -m pytest -v
```

---

## 📂 Fichiers de Configuration

- [`data/sites_config.json`](file:///c:/dev/app/veille%20immo/data/sites_config.json) : Contient la liste de vos recherches actives et leurs critères.
- [`data/seen_announcements.json`](file:///c:/dev/app/veille%20immo/data/seen_announcements.json) : Historique des annonces déjà envoyées (mis à jour automatiquement par GitHub Actions).
- [`vercel.json`](file:///c:/dev/app/veille%20immo/vercel.json) : Configuration du déploiement Vercel.
- [`api/index.py`](file:///c:/dev/app/veille%20immo/api/index.py) : API Serverless Vercel synchronisée avec GitHub.
- [`public/index.html`](file:///c:/dev/app/veille%20immo/public/index.html) : Interface utilisateur responsive Tailwind CSS.
