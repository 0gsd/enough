Bonjour, ici Graham, le créateur d'enough. Ce document -- à part ce passage-ci, je veux dire -- est écrit et maintenu principalement par des agents. Je vais presque certainement y glisser quelques grahamismes de temps à autre, mais l'idée est de ne pas laisser mon propre désir d'écrire des trucs amusants prendre le pas sur une documentation complète.

# le centre d'aide d'enough

> Tout ce que vous pouvez faire avec enough, en un seul endroit. Rédigé pour enough **0.4.1**. Nouveau dans cette passe : **le dictionnaire** — FEED, le dictionnaire anglais maison d'enough : environ 96 000 mots avec leurs sons, leurs familles et leurs histoires, construit sur votre propre machine, à un clic droit de n'importe quel mot que vous lisez, avec de la place à côté pour vos propres mots (section 13) ; **text-planning** comme paradigme d'accueil dans lequel démarre chaque projet, l'ancien paradigme `default` y ayant été absorbé (section 16) ; une brève présentation d'enough, à un clic dans une conversation vide (section 5) ; et un sommaire, une recherche et des liens de section cliquables dans ce manuel (section 10). De la passe précédente : **`/pal`**, où votre readvisor en chef réfléchit d'abord ici, en local, puis envoie une seule question affinée au modèle cloud que vous avez configuré, en vous montrant exactement ce qui a quitté la machine (section 15.3) ; et les conseils qui se terminent en réponse, en document ou en nouvelle composure, avec une charge d'une ligne facultative par readvisor et de quoi reconvoquer un conseil déjà conclu (section 18). De la passe composure : le canevas qui est désormais le plancher de chaque projet, avec la conversation dans un panneau à côté (sections 4 et 5) ; les **readvisors**, c'est-à-dire le nouveau nom des rôles, menés par un readvisor en chef appelé Ed (section 17) ; les **conseils**, où plusieurs readvisors réfléchissent à une seule chose chacun leur tour, par écrit, pendant que vous regardez (section 18) ; et deux compétences, `readvisory` et `scaffold` (section 19). Un projet créé avant cela voit son dossier `rness/roles/` renommé en `rness/readvisors/` la prochaine fois que vous l'ouvrez, avec vos réglages activé/désactivé intacts (section 8). Également là, venu des passes précédentes : l'écran d'accueil (tous les projets que vous avez jamais démarrés, dans une seule liste, avec une porte d'entrée et une porte de sortie — section 2), la passe de conversion (PDF, documents Word, ebooks, présentations et classeurs qui s'ouvrent comme des jumeaux markdown modifiables, avec export, synchronisation, et une visionneuse d'image — section 7), la passe des compétences (le nouveau mode audit d'analyzer, la compétence `anything-finder`, et l'audit au premier usage qui lit toute compétence non fournie par enough avant de l'autoriser), la passe d'août 2026 (sept modèles locaux avec des installations à faisabilité vérifiée, et **enough.app** — l'application de bureau signée et notariée), la passe d'interface de juillet 2026 (la pile de modes, les bulles d'aide par dossier, les reflets girraph→merirmaid), et la passe de préférences 0.3.0 (mise à l'échelle de l'ui et du texte par projet, et l'interface + l'aide en six langues — section 10). Là où ce document et l'application devant vous ne sont pas d'accord, c'est l'application qui a raison et ce document qui a un bug — les corrections sont bienvenues sur [enough.support](https://enough.support).

enough est un système de langage personnel qui tourne sur votre propre machine. Vous le pointez vers un dossier, vous lui parlez, et il vous aide à planifier, écrire, réviser, chercher, et traduire. Les modèles sont locaux par défaut. Vos fichiers restent les vôtres. Et presque tout ce que vous le verrez faire est défini dans de simples fichiers markdown que vous pouvez ouvrir, lire, et modifier.

Gardez une idée en tête pendant votre lecture : **les fonctionnalités intégrées de ce manuel ne sont qu'une fraction de ce qu'enough peut faire.** Les paradigmes, readvisors et compétences fournis d'origine sont un kit de démarrage — des exemples fonctionnels de trois mécanismes de personnalisation, pas leurs limites. Le but ultime, c'est que vous écriviez les vôtres, ou que vous les fassiez écrire par votre readvisor en chef avec vous : un paradigme pour votre façon de planifier des essais, un readvisor qui argumente comme votre lecteur le plus coriace, une compétence qui code votre style maison. La section 3 explique comment. C'est la section la plus importante de ce document, et le manuel n'arrêtera pas de vous y renvoyer.

---

## 1. Installation, raccourcis, et cette documentation

### 1.1 Ce dont vous avez besoin

- Un Mac avec Apple Silicon. (enough est construit et testé sur macOS. Le support Linux est prévu ; Windows est envisageable.)
- De l'espace disque pour au moins un modèle — le plus petit fait environ 5 Go.
- Aucun compte, aucune clé API, aucun abonnement. À moins que vous n'optiez plus tard pour l'emplacement de modèle cloud (section 15.2), tout tourne en local.

### 1.2 Installation

Deux portes, une seule maison.

**L'application — la voie courte.** Téléchargez le DMG `enough` depuis la page des releases, ouvrez-le, glissez **enough** dans Applications, et lancez. macOS signalera qu'il s'agit d'une application venue d'internet — elle est signée et notariée, donc c'est la sympathique boîte de dialogue bleue avec un bouton **Ouvrir**, une seule fois, pas un avertissement à contourner. Un guide de premier lancement prend le relais : il construit son propre environnement Python, vous montre la liste des modèles avec un verdict honnête sur ce qui tient sur *cette* machine (section 15.1), liste les extras optionnels que vous avez déjà, et vous remet à l'écran d'accueil pour choisir le dossier dans lequel vous voulez travailler (section 2). L'essentiel de l'attente, c'est le téléchargement des modèles. Pas de Terminal, pas de Homebrew, pas de git.

L'application embarque son propre moteur d'inférence et Python. Les extras optionnels — saisie vocale, récupération de pages web, vérification grammaticale, traduction — restent des programmes séparés ; la page Extras du guide nomme chacun d'eux, ce qui se désactive sans lui, et comment l'obtenir. Rien n'est obligatoire, et rien ne s'installe dans votre dos. Un extra n'est même pas un programme séparé du tout : la **lecture de PDF** s'installe depuis l'intérieur d'enough quand vous le voulez (section 7.8).

**Le terminal — la voie longue, avec plus de leviers.** Clonez le dépôt, puis double-cliquez sur `install-enough.command` à l'intérieur du clone :

```bash
git clone https://github.com/0gsd/enough.git ~/Downloads/enough-seed
open ~/Downloads/enough-seed
```

La première fois que vous double-cliquez dessus, Gatekeeper de macOS peut renâcler devant un « développeur non identifié » — cette prudence concerne le fichier `.command`, qui n'est pas signé comme l'est l'application. Faites un clic droit sur le fichier et choisissez **Ouvrir** une fois ; macOS retient cette confiance par la suite.

Le lanceur exécute `bootstrap.sh`, un installeur interactif en dix étapes qui demande avant chaque étape et explique ce qu'il s'apprête à faire. Ctrl-C est sûr à tout moment. Le relancer est sûr aussi — il vérifie d'abord l'état et reprend là où vous vous étiez arrêté. Les étapes, en gros :

1. Vérifier votre plateforme.
2. Vérifier la présence de Homebrew, et vous aider à l'installer s'il manque.
3. Installer les programmes auxiliaires sur lesquels s'appuie enough : `llama.cpp` (inférence de modèle locale), `whisper-cpp` (saisie vocale), `tor` (récupérations web anonymisées), et `harper` (vérification grammaticale locale, utilisée par la compétence analyzer). Les convertisseurs de documents — pandoc, pour transformer les pages web récupérées et les fichiers Word en markdown, et typst, pour écrire des PDF — ne sont plus sur cette liste : ils sont fournis à l'intérieur de l'environnement Python propre à enough, installé à l'étape 5, sur toutes les plateformes. Si vous avez par hasard votre propre pandoc installé via Homebrew, enough utilise celui-là à la place.
4. Mettre en place `~/enough/`, le répertoire d'installation global.
5. Préparer l'environnement Python (via `uv`).
6. Télécharger les poids des modèles. Chaque modèle pris en charge est proposé un par un, avec sa taille et une vérification de faisabilité par rapport à la mémoire et à l'espace disque libre de votre machine — ✓ veut dire confortable, ~ veut dire juste, ✗ veut dire cherchez ailleurs. Dites oui à autant ou aussi peu que vous voulez ; la section 15.1 les décrit tous, et tout ce que vous sautez reste une installation en un clic plus tard.
7. Placer le modèle de saisie vocale (whisper).
8. Placer le modèle de traduction hors ligne, utilisé par la compétence `translator`.
9. Mettre la commande `enough` sur votre PATH.
10. Terminé, avec une liste imprimée des prochaines étapes.

Pour mettre à jour plus tard : exécutez `update-enough.command` depuis `~/enough/`, ou tapez `/update-enough` dans le champ de discussion. Quand de nouveaux défauts sortent, enough le mentionne dans l'interface et vous pointe vers cette commande, donc pas besoin d'aller vérifier. `update-weights.command` rafraîchit les poids des modèles séparément.

### 1.3 Lancement

**Depuis l'application :** double-cliquez, et vous atterrissez sur l'**écran d'accueil** — tous les dossiers que vous avez jamais transformés en projet enough, dans une seule liste, avec un moyen d'en ajouter un autre. Choisissez-en un et il s'ouvre. C'est la section 2, et ça vaut la peine de la lire avant celle-ci.

Le menu **enough** contient un seul réglage, **Rouvrir le dernier projet au lancement**, désactivé par défaut : activez-le et l'application saute l'accueil pour vous remettre droit là où vous étiez. Une fenêtre, un projet à la fois — et **Fichier → Fermer le projet** (⌘W) vous ramène à l'accueil dès que vous voulez bouger, sans quitter (section 2.5).

Il reste un simple sélecteur de dossier là-dedans, mais vous ne le croiserez probablement jamais : c'est le repli pour le cas où l'écran d'accueil lui-même ne peut pas s'afficher — une mise à jour à moitié terminée, une installation cassée — pour qu'un mauvais jour vous laisse quand même un chemin vers votre travail.

**Depuis le terminal :** enough tourne par dossier de projet. Ouvrez un terminal dans n'importe quel dossier et exécutez :

```bash
enough
```

puis rendez-vous sur `http://127.0.0.1:3456` (enough l'ouvre pour vous). Dossier différent, projet différent, mémoire différente. Le seul dossier depuis lequel vous ne pouvez pas lancer, c'est `~/enough/` lui-même — la CLI refuse, parce que c'est l'installation, pas un projet.

Vous obtenez aussi l'écran d'accueil, depuis n'importe où :

```bash
enough --home
```

Même écran, même liste, dans votre navigateur au lieu de la fenêtre de l'application. Ouvrez un projet depuis là et le terminal dans lequel vous l'avez démarré devient le terminal de ce projet.

Si vous préférez ne jamais taper la commande, deux lanceurs sont fournis dans `~/enough/shortcuts/` :

- **`enough-on.command`** — copiez-le dans un dossier de projet (`cp ~/enough/shortcuts/enough-on.command ~/some-project/`), puis double-cliquez dessus dans Finder. Une fenêtre Terminal s'ouvre dans ce dossier avec enough en cours d'exécution ; ⌘W ou Ctrl-C l'arrête.
- **`setup-quick-action.sh`** — exécutez-le une fois (`bash ~/enough/shortcuts/setup-quick-action.sh`) et vous obtenez une Action rapide Finder : clic droit sur n'importe quel dossier → Actions rapides → **Launch in enough**. Si l'élément de menu n'apparaît pas, activez-le dans Réglages Système → Clavier → Raccourcis clavier → Services → Fichiers et dossiers.

### 1.4 Cette documentation, et le reste

Ce fichier est le manuel long format. Vous avez aussi :

- **L'aide intégrée** — les bulles `(?)` disséminées dans l'interface, chacune expliquant ce à quoi elle est attachée : un *what*, un *how*, et une liste *ideas*. Voir la section 10.6.
- **Les aide-mémoires** — raccourcis clavier et syntaxe markdown, à un clic dans la fenêtre UI. Voir la section 10.5.
- **[enough.support](https://enough.support)** — le forum communautaire : aide à l'installation, partage de flux de travail, et des gens qui vous aideront volontiers à construire les personnalisations vers lesquelles ce manuel n'arrête pas de vous pousser.

Et tout ça — ce manuel, les bulles, l'interface qui les entoure — se lit en six langues : anglais, français, espagnol, allemand, chinois, et japonais. La section 10.4 présente le menu déroulant et les petits caractères.

---

## 2. L'écran d'accueil

Avant d'être dans un projet, vous êtes sur **l'accueil** : un seul cadre listant tous les dossiers que vous avez jamais transformés en projet enough, plus une tuile pour en ajouter un autre. C'est délibérément l'écran le plus tranquille de l'application. Pas de discussion, pas de barre latérale, pas de modèle, pas de readvisor — rien ne tourne encore et rien n'est en train d'être pensé. Juste vos projets, et le bouton UI ⚙ dans la barre supérieure pour le thème et ce manuel.

Vous le verrez :

- la première fois que vous lancez l'application, quand le guide de premier lancement se termine ;
- à chaque lancement ensuite, à moins que **Rouvrir le dernier projet au lancement** soit activé (section 1.3) ;
- chaque fois que vous fermez un projet (section 2.5) ;
- depuis le terminal, à tout moment, avec `enough --home`.

La seule façon de *ne pas* le voir, c'est ce réglage. Activez **Rouvrir le dernier projet au lancement** et enough retourne directement au projet où vous étiez ; l'accueil ne s'interpose jamais. Désactivez-le et l'accueil est le point de départ de chaque lancement. Cet interrupteur est tout le réglage — il n'y a rien d'autre à configurer.

### 2.1 La grille, la liste, et ¶ W C

Deux vues, basculées par la paire de boutons en haut à droite du cadre, et enough se souvient de laquelle vous préférez.

**Icônes** est la vue de navigation : un glyphe de dossier, le nom du projet, et une ligne toute simple en dessous — *modifié il y a 3 jours*, ou une date une fois que c'est plus vieux qu'une semaine.

**Liste** est la vue de comparaison. Six colonnes :

| colonne | ce que c'est |
|---|---|
| nom | le nom d'affichage du projet (celui que vous définissez dans la barre de titre du projet, ou le nom du dossier) |
| ¶ | paragraphes |
| W | mots |
| C | caractères |
| mis à jour | le changement le plus récent parmi les fichiers que ces comptes couvrent |
| créé | quand le dossier est devenu un projet enough |

Ces trois colonnes du milieu sont les trois mêmes indicateurs qu'enough affiche dans la barre supérieure quand vous avez un document ouvert — ¶ pour les paragraphes (blocs séparés par une ligne vide), W pour les mots, C pour les caractères, espaces et sauts de ligne compris — additionnés sur tout le projet. La règle sur *quels* fichiers sont comptés vaut une phrase, parce que c'est elle qui donne du sens aux chiffres : tout fichier markdown que l'arborescence du projet vous montrerait elle-même, **y compris les jumeaux des documents convertis** (un `.docx` que vous éditez ici, c'est votre écriture), et **rien** de ce qui est à l'intérieur de `rness/` (l'échafaudage propre à enough n'est pas votre livre). Donc le chiffre dans la colonne W, c'est assez précisément la quantité de ce que vous avez écrit.

Cliquez sur n'importe quel en-tête de colonne pour trier selon elle ; cliquez à nouveau sur le même pour inverser. Les projets qui n'ont rien à rapporter — jamais ouverts, jamais comptés — coulent vers le bas dans tous les cas plutôt que de se faire passer pour les plus anciens. L'ordre par défaut est du plus récemment modifié au moins récent.

Un projet dont le dossier n'est pas là en ce moment — un disque externe débranché, un dossier que vous avez déplacé dans Finder — s'affiche grisé, avec le chemin dont il se souvient dans l'infobulle. Il n'est **pas** retiré de la liste, et il garde les chiffres qu'il avait la dernière fois que vous l'avez vu. Un projet sur un disque dans un tiroir n'est pas un projet que vous avez perdu.

### 2.2 Cliquer sur un projet : la carte

Un simple clic n'ouvre pas un projet. Il vous dessine une **carte** de celui-ci : un diagramme merirmaid en lecture seule (section 21) du contenu visible du dossier, avec un petit nœud d'information en haut portant le chemin, le nombre de fichiers, les totaux ¶ et W, et les dates de création, dernière ouverture et dernière modification du projet. C'est le même genre d'image que cacheawl dessine pour un cachebox (section 12.1), pointée sur un projet à la place.

La carte sert pour le moment où vous avez quatre dossiers aux noms plausibles et voulez savoir lequel contient les chapitres. Regardez, puis décidez.

Une fois décidé, le bouton **ouvrir le projet** de la barre d'outils l'ouvre. Esc, ou le ruban en haut à droite, vous ramène à la grille. Et si vous saviez déjà lequel vous vouliez, **double-cliquez** sur la tuile ou la ligne et elle s'ouvre sans détour.

L'ouverture se ressemble dans les deux cas : le chargeur apparaît une seconde ou deux pendant qu'enough éteint l'écran d'accueil et démarre le projet à sa place, et vous voilà dans la vue de discussion (section 4) exactement comme si vous aviez lancé directement dans ce dossier.

### 2.3 Ajouter un dossier

La dernière tuile de la grille — celle avec le plus — c'est comme ça qu'un dossier devient un projet.

Cliquez dessus et macOS ouvre son propre sélecteur de dossier. Choisissez n'importe quel dossier de notes, de brouillons, ou de documents ; enough y ajoute `rness/` (section 8), l'enregistre sur votre écran d'accueil, et l'ouvre. La tuile affiche *en attente du sélecteur de dossier…* pendant que la boîte de dialogue est ouverte, alors prenez tout le temps que vous voulez pour naviguer.

Deux types de dossiers sont refusés, et enough vous dit lequel et pourquoi plutôt que d'échouer vaguement :

- **`~/enough` lui-même, ou tout ce qui est à l'intérieur.** C'est l'installation, pas un projet. (La commande `enough` refuse le même dossier pour la même raison.)
- **Tout ce qui est dans un dossier synchronisé dans le cloud** — Google Drive, Dropbox, iCloud Drive. Ce n'est pas de la pointilleuse ici. Le `rness/` d'un projet est construit à partir de liens symboliques vers les défauts globaux, et les clients de synchronisation réécrivent ou cassent les liens symboliques en routine ; vous vous retrouveriez avec un projet qui arrête discrètement de suivre vos réglages globaux, sur la machine où vous ne l'avez pas remarqué. Gardez les projets sur le disque local et synchronisez plutôt le travail terminé.

Un dossier déjà présent sur votre écran d'accueil n'est pas une erreur — enough l'ouvre simplement.

Si le sélecteur de dossier ne peut pas du tout s'afficher (une machine qui n'est pas un Mac, un bac à sable qui refuse), la modale propose à la place un simple champ de texte où taper le chemin, avec la raison affichée au-dessus. Tout ce qui suit est identique.

### 2.4 Masquer un projet

L'accueil liste tout, pour toujours, et après un an d'expérimentations, ça devient long. Donc : **option-cliquez sur n'importe quelle tuile ou ligne pour la masquer.**

Masquer, c'est une note dans la propre liste d'enough et rien d'autre. C'est ce qu'il dit quand il demande : le dossier sur le disque n'est pas touché, `rness/` n'est pas touché, et pas un mot à l'intérieur ne change. Il n'y a pas de « supprimer ce projet » sur l'écran d'accueil, et c'est délibéré — supprimer un projet, ça veut dire supprimer un dossier plein de votre écriture, et ça, c'est un travail pour Finder, où vous pouvez voir ce que vous faites.

La puce **masqués** à côté des boutons de vue les fait revenir, étiquetée avec leur nombre. Les projets masqués s'affichent grisés avec *masqué* sur leur ligne ; option-cliquez sur l'un d'eux pour le réafficher (aucune confirmation — c'est instantané et instantanément réversible). Dans l'application, vous pouvez actionner le même interrupteur depuis **Affichage → Afficher les projets masqués**.

### 2.5 Fermer un projet, et revenir

Deux portes, une seule pièce.

**Dans l'application :** **Fichier → Fermer le projet**, ou **⌘W**. Le backend du projet s'arrête proprement et l'écran d'accueil apparaît à sa place, une seconde ou deux plus tard.

**Partout, application ou navigateur :** le bouton **fermer le projet → accueil** en haut de la fenêtre UI ⚙ (section 10). Il demande d'abord, parce que fermer met fin à la session — la conversation devant vous est terminée, comme elle le serait en quittant — et vous dépose ensuite exactement au même endroit que le ferait ⌘W.

Ni l'un ni l'autre ne touche votre dossier. Vos fichiers, votre `rness/`, vos fichiers de requête, et vos journaux de session sont tous exactement là où vous les avez laissés ; seule la conversation en cours se termine.

Une conséquence du nouveau ⌘W qui vaut la peine d'être connue si vous utilisez enough depuis un moment : **⌘W ne ferme plus la fenêtre.** enough est une application à une seule fenêtre et fermer cette fenêtre la quitte, donc ⌘Q et le bouton rouge couvraient déjà ce terrain, et ⌘W avait un meilleur travail à faire.

Et une interaction entre ceci et le réglage de réouverture, parce que sinon ça vous surprendra exactement une fois : **fermer un projet ne fait pas oublier ce projet à enough.** Si **Rouvrir le dernier projet au lancement** est activé et que vous fermez un projet, restez un moment sur l'accueil, puis quittez — le prochain lancement rouvre ce projet, pas l'accueil. L'interrupteur est le réglage qui décide où vous commencez ; Fermer le projet est le bouton qui décide où vous êtes maintenant. Si vous voulez désormais commencer sur l'accueil, désactivez l'interrupteur.

### 2.6 Ce que l'accueil retient

Trois petites choses, toutes globales à la machine — elles vous suivent de projet en projet et retour à l'accueil, et elles ne sont stockées dans aucun dossier de projet :

- **Le thème et la police** (section 10.1). L'accueil porte ce que vous avez choisi en dernier, et un thème vers lequel vous basculez *sur* l'écran d'accueil est le thème dans lequel votre projet s'ouvre. C'est celui qui avait l'habitude d'agacer les gens : l'écran de lancement et l'écran de travail sont désormais d'accord, toujours.
- **Icônes ou liste**, de la section 2.1.
- **Si les projets masqués sont affichés**, de la section 2.4.

Tout le reste à propos d'un projet vit dans le dossier de ce projet, où vous pouvez le lire.

---

## 3. Personnalisation du flux de travail à un niveau fondamental

Si vous ne lisez qu'une section, lisez celle-ci.

La plupart des logiciels vous donnent des fonctionnalités. enough vous donne des mécanismes. La personnalité, la méthode et le jeu de compétences de votre readvisor en chef sont assemblés à neuf à chaque message à partir de fichiers markdown posés sur votre disque :

- **`AGENT.md`** — qui est votre readvisor en chef et comment il opère (section 5.3)
- **`MOTIVATION.md`** — le pourquoi : valeurs, priorités, ce à quoi ressemble « terminé »
- **Les politiques** — des règles strictes sur ce qui peut être lu, écrit, et récupéré (section 5.4)
- **Le paradigme actif** — le cadre de raisonnement en vigueur en ce moment (section 16)
- **Les compétences activées** — des capacités auxquelles il peut faire appel (section 19)
- **Les readvisors activés** — d'autres jugements fondus dans la voix, ou assis à un conseil (section 17)
- **Le profil du projet** — ce qui a été appris sur ce projet (section 8.1)

Modifiez n'importe lequel de ces éléments, dans l'application ou dans n'importe quel éditeur de texte, et le changement prend effet au message suivant. Pas de recompilation, pas de redémarrage, pas d'API de plugin. Si vous savez écrire un fichier markdown, vous savez reprogrammer vos readvisors.

### 3.1 Global contre local au projet

Tout ce qui est personnalisable suit un seul motif : **les défauts vivent dans `~/enough/defaults/`, les projets s'y lient, et n'importe quel projet peut rompre le lien.**

Modifiez un fichier dans `~/enough/defaults/` et tout projet encore lié à lui récupère le changement. Dans un projet, ouvrez un fichier lié et cliquez sur **personnaliser** — le lien devient une copie locale au projet, et à partir de là ce projet fait sa propre route pendant que les autres continuent de suivre le défaut global. L'arborescence des fichiers vous dit lequel est lequel d'un coup d'œil : les fichiers liés s'affichent *en italique et atténués*, les copies locales s'affichent normalement.

Les nouvelles compétences et les nouveaux paradigmes déposés dans `~/enough/defaults/` apparaissent dans tous les projets au lancement suivant ; les readvisors ont en plus un foyer inscriptible bien à eux, `~/enough/readvisors/` (section 17). Compétences et readvisors arrivent désactivés, donc rien ne change dans votre dos ; vous les activez par projet quand vous les voulez. Une compétence qu'enough n'a pas fournie — une que vous avez téléchargée, une qu'un ami vous a envoyée, une écrite pour vous au cours d'une séance — est lue avant d'être autorisée à entrer. La section 19.9 couvre ce sujet.

### 3.2 Les trois types de composants

| | Paradigme | Compétence | Readvisor |
|---|---|---|---|
| Ce que c'est | Un cadre de raisonnement — comment le travail est abordé | Une capacité ciblée — vocabulaire, recettes, procédures | Un second jugement — son propre AGENT.md + MOTIVATION.md |
| Combien actifs | Exactement un à la fois | N'importe quel nombre activé | N'importe quel nombre activé |
| Vit à | `rness/paradigms/<nom>.md` | `rness/skills/<nom>/SKILL.md` | `rness/readvisors/<nom>/` |
| Exemples fournis | text-planning (l'accueil), translation, workflow-design | analyzer, anything-finder, girraph-merirmaid, lexicographer, memoir-dialectic, readvisory, scaffold, translator | block-breaker, open-skeptic |

### 3.3 Construire les vôtres

Vous pouvez écrire ces fichiers à la main — ce sont du markdown avec un petit bloc YAML en tête — mais vous n'êtes pas obligé. Le **paradigme workflow-design** fourni d'origine (section 16.3) existe pour que votre readvisor en chef puisse les construire avec vous. Dites « construis-moi une compétence qui… » ou « fais-moi un paradigme pour… » et il bascule vers workflow-design, pose ses questions de clarification (périmètre ? nom ? conditions de déclenchement ? fichiers compagnons ?), et écrit le composant correctement, frontmatter `description:` comprise, celle qui indique aux tours futurs quand y faire appel. Les readvisors ont leur propre porte d'entrée — la compétence `readvisory` (section 19.6), qui interroge une personne plutôt qu'une spécification.

Ce que les gens construisent réellement :

- Un **paradigme** pour chaque mode distinct de leur travail — recherche, rédaction, révision — avec des règles explicites pour savoir quand changer.
- Une **compétence** qui code la voix d'une newsletter, un format de citation, la terminologie d'une thèse.
- Un **readvisor** qui est un canard en plastique posant des questions socratiques, ou un relecteur sceptique, ou l'ami dont ils apprécient le plus le goût, interrogé une fois et gardé.

Le reste de ce manuel décrit les composants intégrés. Lisez chacun d'eux comme un exemple travaillé que vous avez le droit de copier, forker, et améliorer.

---

## 4. Composure — la base de la pile

Ouvrez un projet et vous atterrissez sur une **composure** : un canevas qui remplit la fenêtre, avec la conversation dans un panneau à côté (section 5). C'est le rez-de-chaussée. Ce n'est pas un mode qu'on ouvre et qu'on quitte — tous les autres modes s'empilent par-dessus et finissent par se refermer dessus, et il n'y a aucun moyen de le fermer, parce qu'il n'y aurait rien en dessous. (L'*écran d'accueil* de la section 2 est tout autre chose : c'est là que vous êtes avant qu'un projet soit ouvert ; ici, c'est là que vous êtes une fois qu'il l'est.)

Une composure est un fichier `.comp` : des boîtes de texte, et de l'encre à main levée, sur un plan de travail sans bord que vous faites glisser et que vous zoomez. Les boîtes s'appellent des **modules**. Il n'y a pas de bouton enregistrer — tout s'écrit au fil de l'eau — et le fichier lui-même est du HTML ordinaire : un `.comp` s'ouvre donc comme une page simple et lisible dans n'importe quel navigateur, sur une machine où enough n'est pas installé du tout. Ce n'est pas un effet de bord. Un document que vous ne pouvez lire que dans le programme qui l'a fabriqué est un document que vous avez prêté à quelqu'un.

Ce qu'il y a autour :

- **La barre d'outils**, en haut du canevas : le titre de la composure (tapez dedans, cliquez ailleurs, c'est renommé), le sélecteur lecture/édition, les outils, **ajouter un module**, annuler et rétablir, le groupe de zoom, la recherche, l'interrupteur des commentaires, et le menu **composures** — nouvelle à partir d'un form…, ouvrir…, enregistrer comme form….
- **La barre latérale.** L'arborescence des fichiers du projet, plus les sections de contrôle : le **paradigme** actif, les interrupteurs des **compétences** et des **readvisors**, et vos **requêtes**. Option-cliquez n'importe quel fichier ou dossier pour un menu contextuel (nouveau fichier, nouveau dossier, copier le chemin, copier le nom). ⌘\ masque et affiche toute la barre latérale.
- **La barre du haut.** Les boutons de la fenêtre de modèle, du broker, de la fenêtre UI, de wikisink (🚰), et de cacheawl ; les indicateurs des modes actuellement empilés (section 14) ; et, tout à droite, l'interrupteur du panneau readvisor.

### 4.1 Se déplacer

**Faites glisser** avec un défilement à deux doigts, en maintenant la barre d'espace, ou avec le bouton du milieu de la souris. **Zoomez** par pincement, avec ⌘-molette autour du pointeur, avec ⌘+ / ⌘− / ⌘0, ou avec **ajuster**, qui cadre tout ce que vous avez et le centre. L'affichage du zoom dans la barre d'outils est un bouton : cliquez-le pour revenir à 100 %.

Trois choses déplacent la vue toutes seules, et les trois essaient de vous aider.

**L'ajustement, chaque fois que la place change.** Sur un tableau — toute composure qui n'a pas la forme d'une page — un changement de l'espace dont dispose le canevas se termine exactement là où **ajuster** vous mettrait : tout en vue, centré. Masquez la barre latérale, ouvrez ou fermez le panneau readvisor, donnez-lui toute la fenêtre puis reprenez-la, ouvrez les commentaires, redimensionnez la fenêtre, changez l'échelle de l'ui : un instant après que le changement se stabilise, le tableau aussi. Il sait attendre, également. Il ne prend jamais la vue pendant que vous faites glisser, pincez ou défilez, et tant qu'un mode est empilé sur la composure il se retient jusqu'à ce que vous redescendiez jusqu'à elle. Zoomer à la main marche toujours comme avant ; cela dure jusqu'à la prochaine fois que la place change.

**Les paliers de panneau.** Sur une page, masquer un panneau latéral ne fait pas qu'élargir le canevas, ça l'*agrandit* : le texte d'une page se lit vers 12 points avec la barre latérale et le panneau readvisor ouverts, vers 14 avec l'un des deux masqué, et vers 16 avec les deux. Le changement s'anime sur un cinquième de seconde, ancré sur votre curseur si vous êtes en train de taper et sur le milieu de la vue sinon, pour que vous ne perdiez pas votre place.

**L'ajustement de page.** Une composure en forme de page — vierge, journal, conseil — est centrée et tenue au zoom qui fait tenir toute sa largeur, avec une marge confortable, jusqu'à la première fois que vous zoomez à la main. Une fenêtre plus large montre plus de plan de travail autour de la feuille plutôt qu'une feuille plus grande. Seule la largeur est ajustée : une page est plus haute que la plupart des fenêtres, donc le bas d'une page est toujours à un glissement de distance. Quand la place change, une page garde cet arrangement — largeur réajustée, feuille recentrée, position de lecture là où elle était — plutôt que d'être rétrécie pour montrer d'un coup toute une longue feuille.

**Les faces.** Dézoomez assez loin et chaque module se replie sur sa **face** : son titre, composé aussi grand que la boîte le permet, avec le corps en faux-texte. Soixante cartes se lisent donc comme soixante titres au lieu de soixante rectangles gris, et un tableau que vous avez construit à taille de lecture reste un tableau d'un coup d'œil. Donnez un titre à un module et c'est vous qui décidez ce que dit cette face. L'encre, de son côté, s'amincit plus lentement que tout le reste ne rétrécit : un croquis vu de loin se lit encore comme un croquis.

### 4.2 Les quatre outils

Le sélecteur lecture/édition fonctionne comme partout ailleurs dans enough : un œil pour lire, un crayon pour modifier. Les outils n'existent que dans la face édition, et chacun a sa lettre.

- Le **pointeur (V)** sélectionne. Cliquez un module, glissez-le pour le déplacer, glissez une poignée pour le redimensionner, tracez un rectangle sur le plan de travail vide pour en attraper plusieurs. Maj-clic en ajoute ou en retire un. Les flèches décalent finement ; maintenez maj pour un pas plus grand. Suppr retire — avec un avertissement d'abord s'il y a du texte dedans, et ⌘Z pour revenir en arrière. Double-cliquez un module texte et vous voilà dans l'outil texte à l'intérieur.
- Le **texte (T)** place le curseur dans un module texte. Il ne sait pas fabriquer de boîtes, et cliquer sur le plan de travail vide ne fait rien ; c'est le travail du bouton d'ajout de module. Dans une page, vous avez le gras et l'italique, les niveaux de titre, les listes, les listes à cocher, les citations, le code, les liens et les quatre couleurs de surlignage — avec le markdown que vous tapez déjà : `# `, `- `, `1. `, `[] `, `> ` et un bloc encadré se transforment en la vraie chose à mesure que vous les tapez. Tout ce que vous collez est d'abord ramené à une structure simple.
- Le **crayon (P)** dessine. Dessinez, tout simplement ; le trait est lissé et simplifié quand vous relâchez. Maintenez **maj** pendant que vous glissez et vous obtenez un segment droit terminé par une pointe de flèche, ce qui est la façon de dire *ceci, puis cela*.
- La **gomme (E)** efface. C'est un cercle qui garde la même taille à l'écran quel que soit le zoom. Faites-la passer sur un trait et la partie sous le cercle disparaît, laissant les deux bouts derrière comme deux traits séparés ; ⌘Z remet le trait d'un seul tenant.

L'encre est posée sur le plan de travail, *sous* les modules : une note peut donc traverser trois cartes et une flèche en relier deux. Attrapez un trait avec le pointeur en cliquant juste à côté, et l'inspecteur propose les cinq couleurs d'encre — encre, rouge, bleu, vert, jaune — et une suppression.

### 4.3 Les modules : les six types

Un module **texte**, c'est de l'écriture, avec autant de pages à l'intérieur que vous voulez. Les cinq autres pointent vers quelque chose, vous en montrent un aperçu en direct pendant que vous lisez, et ouvrent la vraie chose quand vous cliquez :

- **un fichier de ce projet** — ses premières lignes, et un clic l'ouvre exactement comme le clic dans l'arborescence l'aurait fait (documents convertis compris). Pointez-en un vers un `.comp` et le clic échange le canevas sous vos pieds, ce qui est précisément ce qui transforme un tableau en descente par paliers.
- **un article wikisink** — les paragraphes d'introduction, et un clic ouvre le lecteur wikisink à cet endroit (section 11). Sur une machine sans archive, la carte le dit, garde le nom de l'article, et se remplit toute seule dès qu'une archive est installée.
- **un lien vers le web** — le titre et l'hôte. Un clic l'ouvre dans votre navigateur, comme tout autre lien externe de l'application.
- **une page web en cache** — le texte de la page tel qu'à la dernière récupération, avec la date et un bouton **actualiser**. L'actualisation passe par le broker exactement comme n'importe quelle autre lecture web : vos interrupteurs de récupération, vos listes blanches et votre routage Tor s'appliquent tous — et si le broker refuse, la carte vous montre son refus dans les mots mêmes du broker, pour que vous sachiez quel interrupteur aller regarder.
- **une image** — l'image, mise à l'échelle de la boîte. Un clic ouvre la visionneuse d'image (section 7.9).

**ajouter un module** ouvre une courte liste des six. enough place et dimensionne le nouveau pour vous, près de ce que vous regardiez, et le sélectionne.

### 4.4 L'inspecteur

Sélectionnez quelque chose dans la face édition et un petit panneau apparaît à côté — jamais par-dessus — avec tout ce qui s'applique :

- **Dix pastilles de fond** : papier, jaune, rose, bleu, vert, orangé, lilas et gris, plus **encre**, qui est une carte sombre, et **transparent**, qui n'est pas une carte du tout. Les deux dernières servent à la structure : une carte sombre pour une ligne de titre, une transparente pour une étiquette qui ne doit pas ressembler à une note.
- **La taille du texte**, plus petit et plus grand, pour ce module seulement.
- **Les pages** : en ajouter une, en retirer une. Un module de plus d'une page porte des boutons de changement de page et une étiquette `n / N`, et un texte qui déborde d'une page propose **continuer sur une nouvelle page →** plutôt que de grandir indéfiniment en silence.
- **L'ordre** : mettre au premier plan, mettre à l'arrière-plan.
- **Le champ propre au type**, quand il y en a un — un sélecteur de fichier qui cherche dans l'arborescence du projet à mesure que vous tapez, une zone de recherche wikisink, un champ d'adresse, une politique d'actualisation.
- **Commenter ce module**, et **supprimer**.

Sélectionnez plusieurs modules et l'inspecteur dit combien il y en a et propose ce qui a encore du sens.

### 4.5 Les forms, et enregistrer les vôtres

Un **form** est un modèle de composure. Cinq sont fournis :

- **blank** — une seule feuille en forme de page, qui s'ouvre dans la face édition avec le curseur déjà en train de clignoter dedans.
- **cards** — un tableau de cartes de texte en grille, qui s'ouvre dézoomé pour tout montrer.
- **scaffold** — un tableau disposé en colonnes de temps forts, avec un bandeau en haut pour la prémisse et une rangée en bas pour les fins. C'est ce que la compétence `scaffold` (section 19.7) remplit quand elle transforme un tas de notes en structure.
- **journal** — un registre daté. Un module, une entrée par page. Ouvrir un journal vous pose sur la page d'*aujourd'hui*, curseur dedans, et cette page n'existe qu'en mémoire jusqu'à ce que vous tapiez quelque chose : ouvrir le journal puis se raviser ne laisse donc rien derrière. L'entrée s'enregistre au fil de l'eau ; partez sans la classer et le journal rouvre sur ce même brouillon inachevé. **classer cette entrée** l'estampille de la date et la rend définitivement en lecture seule — enough refusera de la modifier ensuite et le curseur n'y entrera plus — et vous fait passer à une page neuve. Refeuilleter les entrées classées ne risque rien : tourner une page où vous n'avez pas écrit n'enregistre rien du tout. Vous pouvez toujours commenter un texte classé, ce qui est bien tout l'intérêt de le classer.
- **council** — une salle de readvisors qui réfléchissent à une seule chose chacun leur tour. C'est la section 18.

**enregistrer comme form…**, dans le menu des composures, garde la composure que vous regardez comme un form à vous. Il atterrit dans `rness/composure-forms/` et rejoint la liste à partir de là, dans ce projet. Un form à vous qui porte le nom d'un form fourni l'emporte.

### 4.6 Recherche, commentaires, et revenir en arrière

**La recherche** lit le texte brut de chaque module et de chaque page — ou d'un seul module, quand exactement un est sélectionné. Entrée et maj-Entrée parcourent les résultats, avec un compteur à côté du champ. Un résultat est un *endroit*, pas un surlignage : le canevas glisse jusqu'à lui, tourne à sa page si elle est ailleurs, et clignote brièvement sur les mots. Rien dans votre texte n'est touché pour vous montrer où il est. Échap efface la requête.

**Les commentaires** fonctionnent comme ceux de wikisink (section 11.2), sur les mêmes cartes. Sélectionnez du texte dans un module et commentez-le, ou commentez un module entier depuis l'inspecteur ou le menu qu'ouvre un clic droit dessus ; le bouton des commentaires dans la barre d'outils ouvre le panneau. Répondre, résoudre, rouvrir, sauter. Un texte que vous modifiez ensuite est ré-épinglé à son module ; un module carrément supprimé laisse le commentaire **orphelin** dans le panneau, étiqueté comme tel, jamais discrètement jeté. Les commentaires vivent dans un fichier caché à côté du `.comp` plutôt que dedans, pour que la composure elle-même reste propre — et ils fonctionnent sur des choses que vous ne pouvez pas modifier du tout, comme une page de journal classée ou une intervention de conseil.

**Annuler** est ⌘Z, rétablir ⇧⌘Z, jusqu'à cent pas par composure ouverte. À l'intérieur d'une page de texte, c'est l'annulation de votre navigateur qui prend le relais, et c'est la bonne à cet endroit.

### 4.7 Où vivent les composures, et ce qui s’ouvre au lancement

Les nouvelles composures atterrissent dans `rness/io/composure/`, nommées d'après leur titre et la date. Ce sont des fichiers ordinaires : copiez-les, mettez-les sous git, envoyez-en un à quelqu'un qui n'a jamais entendu parler d'enough.

Rien n'est écrit tant que rien n'a été écrit *dedans*. Une composure que vous ouvrez sans jamais y toucher ne laisse aucun fichier derrière — pas même un fichier vide. Dès qu'il y a quelque chose à enregistrer, l'état d'enregistrement dans la barre d'outils vous tient au courant : *enregistrement…*, puis *enregistré*, ou *pas enregistré — nouvelle tentative* si le serveur est brièvement injoignable, ce qui est le message honnête plutôt qu'un mensonge silencieux.

La composure sur laquelle vous atterrissez, c'est à vous de la régler. La fenêtre **projet** — celle avec le nom, la description et le dossier du projet — porte une ligne **au lancement, ouvrir** avec quatre réponses : *une nouvelle page vierge*, *la dernière composure utilisée*, *une composure précise…*, ou *une nouvelle à partir d'un form…*. Si la chose que vous aviez désignée a depuis été renommée ou supprimée, enough ouvre une page vierge et le dit en une ligne, plutôt que de vous claquer la porte au nez à l'entrée.

Et n'importe quel `.comp` de l'arborescence s'ouvre d'un clic. Il ne s'empile pas par-dessus ce que vous faites — il *devient* ce que le canevas affiche, parce qu'il n'y a jamais qu'un seul plancher.

### 4.8 Jeter un œil sous la pile

Les indicateurs de la pile de modes dans la barre du haut (section 14) se terminent par un carré permanent pour la composure. Il n'a pas de ruban de fermeture, parce qu'il n'y a rien à fermer.

Cliquez-le pendant que des modes sont empilés et tous se masquent, vous montrant le canevas en dessous avec leur état exactement tel qu'il était — votre position de défilement, vos modifications non enregistrées, votre descente dans un girraph imbriqué. Cliquez-le de nouveau, ou cliquez n'importe quel autre indicateur, et ils reviennent aussitôt. Échap pendant le coup d'œil restaure d'abord la pile, et ne la dépile qu'ensuite.

C'est pour le moment où la chose que vous devez vérifier est sur le tableau et où vous n'avez pas envie de démonter trois modes pour la voir.

### 4.9 Ce que vos readvisors peuvent faire à une composure

Ils peuvent en lire une, en fabriquer une à partir d'un form, ajouter, restyler et réorganiser des modules, écrire une page, enregistrer une composure comme form, et — avec la compétence `scaffold` (section 19.7) — transformer tout un plan en tableau disposé, d'un seul geste. Tout cela est conditionné par l'interrupteur **composure tools** du broker (section 9) ; votre propre canevas n'est jamais conditionné, de la même façon que votre propre navigation dans wikisink et cacheawl ne l'est jamais.

Ce qu'ils ne peuvent pas faire, c'est écrire un `.comp` comme fichier. Les deux portes ordinaires d'écriture de fichier refusent l'extension tout net : chaque changement qu'un readvisor apporte passe donc par le même petit jeu d'opérations que vous utilisez, une à la fois, par la même porte, dans le registre. Ça veut dire qu'un modèle qui s'embrouille ne peut pas corrompre un document — le pire qu'il puisse faire est d'ajouter une carte dont vous ne vouliez pas, et ⌘Z est juste là.

Quand un readvisor modifie un module pendant que vous regardez la composure, il se rafraîchit sur place avec un bref clignotement. Le seul module qui n'est jamais rafraîchi sous vos yeux est celui dans lequel vous êtes en train de taper.

---


## 5. Le panneau readvisor

La conversation vit dans une colonne le long du bord droit, à côté de ce sur quoi vous travaillez plutôt qu'à sa place. Votre **readvisor en chef** est nommé en haut — **Ed**, jusqu'à ce que vous le renommiez (section 17) — avec les autres readvisors que vous avez activés listés à côté de lui. En conversation ordinaire, ils répondent d'une seule voix, nourrie de toutes ces perspectives ; un conseil (section 18), c'est là qu'ils parlent séparément.

Tapez un message et faites ⌘Entrée, ou cliquez le bouton d'envoi. Les réponses arrivent en flux continu, et enough peut agir pendant que votre readvisor parle — lire et écrire des fichiers, lancer des commandes shell, récupérer des pages — chaque appel d'outil apparaissant dans la transcription au fur et à mesure. Le **bouton micro** dicte : la parole est transcrite localement par whisper.cpp, votre voix ne quitte jamais la machine, et le bouton pulse pendant l'enregistrement. Cliquez de nouveau pour arrêter.

Les deux voix restent chacune de leur côté de la colonne : vos messages se collent au bord gauche, ceux de votre readvisor en chef au bord droit, chacun avec un fin filet de sa propre couleur le long du bord extérieur, si bien qu'un long échange se lit encore comme un échange d'un coup d'œil. Seuls les blocs bougent — le texte à l'intérieur reste aligné à gauche, parce qu'une prose alignée à droite est pénible à lire. Les notes propres d'enough (un refus, une suggestion, la question qu'un `/pal` a envoyée) occupent toute la largeur, puisqu'elles ne sont la voix de personne.

**Une brève présentation.** Une conversation vide en propose une : un petit lien, *une brève présentation d'enough*, sous la ligne d'attente. Cliquez dessus, ou tapez `/intro` à n'importe quel moment, et votre readvisor en chef affiche une courte visite — ce qu'est un projet, la composure, lecture/édition, les readvisors, les paradigmes, le dictionnaire et le reste de la référence locale, et où se trouve le manuel complet. Aucun modèle ne l'écrit : elle arrive donc d'un coup et dit chaque fois la même chose. Demandez « que sais-tu faire ? » ou « qu'est-ce qu'enough ? » comme tout premier message et vous obtenez la même présentation ; plus tard dans une conversation, ces questions vont à votre readvisor comme n'importe quelle autre, parce qu'alors « c'est quoi, ça ? » désigne en général quelque chose à l'écran. Et si vous ouvrez par un simple bonjour, votre readvisor en chef peut proposer la présentation avant toute autre chose. Elle suit la langue de votre interface quand une traduction existe, et elle est en anglais sinon.

### 5.1 Ancré, plein écran, fermé

Trois états, un seul interrupteur tout à droite de la barre du haut.

**Ancré** est l'état par défaut, et celui dans lequel vivre. C'est une vraie colonne à côté du canevas — ou à côté de n'importe quel mode que vous avez empilé par-dessus — vous n'avez donc jamais à fermer ce que vous lisez pour poser une question dessus. Sur une fenêtre trop étroite pour ça, où l'ancrage réduirait la scène en dessous d'environ 480 pixels, le panneau flotte au-dessus du bord droit de la scène au lieu de la comprimer davantage.

**Plein écran** donne toute la fenêtre au panneau, avec la conversation centrée dans une colonne lisible. C'est le clin d'œil au passé : l'ancienne vue Discussion, pour quand la réponse est longue et que vous voulez vous asseoir avec.

**Fermé** est une colonne de largeur nulle. Un tour qui se termine alors que le panneau est fermé pose un point sur son bouton dans la barre du haut — *quelque chose est arrivé pendant que vous regardiez ailleurs*, et non *voici une bonne réponse* — et ouvrir le panneau l'efface.

⌘/ ouvre et ferme. ⇧⌘/ lui donne toute la fenêtre, et ⌘/ le ramène. ⌘K met toujours le focus sur la zone de message, en ouvrant le panneau au passage s'il était fermé. Échap fait retomber un panneau plein écran en panneau ancré — mais Échap est inerte tant que le curseur est dans la zone de message, et ouvrir le panneau l'y place, donc cliquez ailleurs d'abord. **Échap ne ferme jamais un panneau ancré**, délibérément : ce serait la seule touche que tout le monde appuie par accident.

Ouvert ou fermé est retenu par projet, dans les fichiers de ce projet, et appliqué avant le premier rendu de la fenêtre, pour que rien ne sursaute au lancement. Le plein écran est un geste plutôt qu'un réglage, et n'est jamais retenu.

**Une exception, et c'est un conseil.** Tant qu'un conseil est sur le canevas (section 18), le panneau est tenu fermé et son interrupteur est désactivé, avec une infobulle qui dit pourquoi : les conseils et la discussion partagent un seul modèle, et il n'y en a qu'un. Quitter le conseil vous rend le panneau exactement comme vous l'aviez — votre propre préférence est retenue, pas écrasée.

### 5.2 Envoyer une sélection

Sélectionnez du texte partout où le panneau peut le voir — un document en lecture/édition, un article wikisink, un module sur une composure — et une pastille apparaît au-dessus de la zone de message, nommant sa provenance et en citant le début. Envoyez, et ce passage part avec votre message, encadré, étiqueté avec exactement ce que disait la pastille. Le × de la pastille la retire.

Joindre vaut mieux que décrire. Les mots exacts traversent, et on dit à votre readvisor d'où ils viennent plutôt que de le laisser aller chercher. Et rien d'*autre* n'est joint : un mode resté ouvert derrière le panneau ne s'appose pas discrètement sur chaque message que vous envoyez. Ce que vous avez choisi est ce qui part.

### 5.3 AGENT.md et MOTIVATION.md

Chaque projet porte sa propre copie de ces deux fichiers dans `rness/`. Ils sont la racine de l'identité de votre readvisor en chef ici, et tous deux sont chargés à chaque tour.

**`AGENT.md`**, c'est le *comment* : les instructions de travail. Ton, garde-fous, conventions, consignes permanentes. « Garde la prose en minuscules. » « Ne touche jamais aux fichiers de `archive/`. » « Demande avant de lancer une commande shell de plus d'une ligne. »

**`MOTIVATION.md`**, c'est le *pourquoi* : les valeurs et les priorités au-delà de la tâche du moment. À quoi sert le projet, qui il sert, quels arbitrages comptent (la justesse avant la vitesse ? la brièveté avant l'exhaustivité ?), à quoi ressemble « terminé ».

Cliquez sur l'un ou l'autre fichier dans la barre latérale pour le lire ; appuyez sur **personnaliser** pour forker votre copie locale au projet, ou modifiez-le dans l'éditeur de votre choix. Les changements prennent effet au message suivant. Tous les autres readvisors utilisent ces deux mêmes fichiers (section 17) — le chef n'est pas d'une autre nature, il est seulement celui qui parle par défaut.

### 5.4 Le dossier des politiques et les listes blanches

`rness/policies/` contient les règles strictes. Pas de la personnalité — de la loi. Quatre politiques sont fournies d'origine :

- **`allowlists.md`** — les règles de portée. Trois listes :
  1. *Préfixes de lecture de fichiers :* les chemins absolus que vos readvisors peuvent lire en dehors du projet (par défaut : `~/enough/`).
  2. *Préfixes de lecture-écriture :* les chemins où ils peuvent aussi écrire en dehors du projet. Cette liste est fournie **vide** : d'origine, rien n'est écrit en dehors de votre projet, et ça le reste tant que vous n'ajoutez pas délibérément un chemin.
  3. *Domaines internet :* les hôtes récupérés directement (les défauts incluent `gutenberg.org`, `en.wikipedia.org`, `en.wikisource.org`, `archive.org`, `standardebooks.org`, et l'hôte de téléchargement de Kiwix). Un domaine absent de la liste n'est pas bloqué — la récupération est routée par un proxy Tor local à la place, pour qu'une recherche ponctuelle ne laisse pas votre adresse dans les journaux d'un serveur. Un interrupteur du broker peut désactiver ce repli, et les récupérations hors liste échouent alors franchement.
- **`context-management.md`** — comment une fenêtre de contexte qui se remplit est repérée, et comment en sortir proprement sans perdre l'état (section 8.3).
- **`requests.md`** — quand et comment le travail de longue haleine est suivi sous forme de fichiers de requête (section 8.3).
- **`profile-maintenance.md`** — ce qui a sa place dans le profil du projet et ce qui n'y en a pas (section 8.1).

Les politiques sont liées par symlink depuis les défauts comme tout le reste : vous pouvez donc resserrer la liste blanche globalement, ou la personnaliser pour un projet qui a besoin d'une portée plus large (ou plus étroite). Modifier `allowlists.md` est en pratique la personnalisation la plus courante : ajoutez les sites de documentation auxquels vous faites confiance, ajoutez un dossier partagé où vos readvisors devraient pouvoir écrire, et vaquez à vos occupations.

---




## 6. Mode lecture/édition

Cliquez sur n'importe quel fichier dans l'arborescence et il s'ouvre dans le mode lecture/édition unifié : un mode à deux *faces* — une **face lecture** (l'œil) pour relire, une **face édition** (le crayon) pour changer le texte.

### 6.1 Plein contre mini, et basculer entre tout

Lecture/édition existe en deux tailles. **Mini** est un panneau latéral à côté de la discussion : gardez un document de référence sous le coude pendant que vous conversez. (Le mini panneau omet délibérément la barre d'outils de révision — il est fait pour la lecture et les modifications rapides, pas le balisage.) **Plein** prend tout le cadre, pour les documents longs et l'édition sérieuse.

Changez de taille avec le bouton mini↔plein dans l'habillage du panneau. Changez de face avec le bouton de bascule de face juste à côté. ⌘S enregistre dans la face édition. Quand ce que vous regardez est le jumeau d'un document converti, l'habillage nomme aussi l'original et porte un bouton **exporter** pour réécrire vos changements dedans (section 7.5). Et tout est protégé contre la perte : si vous avez des modifications non enregistrées, enough vous prévient avant de laisser quoi que ce soit les abandonner — naviguer vers un autre fichier, fermer le mode, rebondir vers un autre document. Vous ne perdrez pas une heure de travail à cause d'un clic malheureux.

Pendant qu'un document est ouvert, trois compteurs apparaissent dans la barre supérieure et suivent votre frappe : **¶** paragraphes, **W** mots, **C** caractères. (La vue liste de l'écran d'accueil vous montre les trois mêmes totaux pour tout un projet — section 2.1.) Quand la fenêtre se rétrécit, les boutons et les indicateurs de mode gardent leur place : le nom du projet raccourcit d'abord, jusqu'à une dizaine de caractères environ, et ce n'est qu'ensuite que les compteurs s'effacent, de droite à gauche.

Comme chaque mode plein cadre, lecture/édition affiche son icône dans la zone d'indicateurs en haut à droite, avec un petit ruban croix-rouge accroché pour fermer (section 14).

### 6.2 Surlignage

Dans la face lecture de n'importe quel document markdown, sélectionnez du texte et peignez-le d'une des quatre couleurs — **jaune, vert, bleu, rose** — depuis la barre d'outils ou le popup qui apparaît au-dessus d'une sélection. La même barre d'outils propose une mise en forme légère : gras, italique, souligné (⌘B / ⌘I / ⌘U).

Les surlignages sont durables, et ils vivent hors bande : chaque document reçoit un fichier annexe caché (`.<nomdufichier>.highlights.json`) plutôt que du balisage épissé dans votre texte, si bien que le document lui-même reste propre. Une bande colorée dans la marge marque chaque ligne surlignée. Les surlignages persistent d'une session à l'autre, et les couleurs superposées s'empilent.

Voici la partie qui change votre façon de travailler : vos readvisors peuvent les voir. L'outil `read_highlights` liste chaque surlignage d'un document par couleur, et `navigate_to_highlight` fait sauter la vue vers l'un d'eux. Ça transforme le surlignage en canal de communication. Peignez en jaune les quatre paragraphes que vous voulez réécrits et en vert les deux que vous adorez, puis dites « réécris les parties jaunes ; garde le ton des vertes ». Quand vous mentionnez une couleur, votre readvisor comprend que vous parlez de vos surlignages.

### 6.3 Types de fichiers pris en charge

- **Markdown (`.md`)** s'affiche mis en forme dans la face lecture et comme source dans la face édition. Markdown est la langue maternelle d'enough — presque tout ce que le système lui-même écrit est du markdown.
- **Le texte brut**, et tout ce qui y ressemble, s'ouvre en lecture/édition comme du texte.
- Les fichiers **`.girraph`** s'ouvrent en mode girraph à la place (section 20).
- Les fichiers **`.merirmaid`** s'ouvrent en mode merirmaid à la place (section 21).
- Les **articles Wikipédia enregistrés** (`article.html` à l'intérieur d'un dossier `wiki/`) s'ouvrent dans le lecteur wikisink en fidélité complète (section 11.2).
- **Documents Word, PDF, ebooks, présentations, classeurs** s'ouvrent comme un **jumeau** markdown modifiable — une ligne dans l'arborescence, un clic, et un bouton **exporter** dans l'habillage pour réécrire vos changements en retour. C'est la section 7, et c'est toute l'histoire.
- Les **images** (`.png`, `.jpg`, `.gif`, `.webp`, `.bmp`, `.svg`) s'ouvrent dans une visionneuse simple (section 7.9). Les images *à l'intérieur* d'un document s'affichent dans la face lecture comme n'importe quelle autre image en markdown.

enough reste un système de texte, et le restera : il affiche du markdown, pas de la mise en page. Ce qu'il fait avec tout le reste, c'est le convertir — assez sans perte pour qu'on puisse y travailler, assez honnêtement pour vous dire ce qui n'a pas survécu.

---

## 7. Travailler avec des PDF, documents Word, et autres fichiers

enough n'affiche pas un PDF, ne met pas en page un document Word, ne dessine pas un tableur, et ne prétend pas le faire. Ce qu'il fait à la place est plus discret et, pour le genre de travail que vous faites ici, plus utile : il convertit le document en markdown que vous pouvez réellement lire, modifier, surligner, et remettre à vos readvisors — et il garde ce markdown lié à l'original, pour que vos changements puissent y retourner.

Rien de tout ça n'est un mode séparé ni une application séparée. Vous cliquez sur le fichier. Il s'ouvre.

### 7.1 Le jumeau

Ouvrez `memo.docx` et enough écrit `memo.docx.md` à côté. Ce second fichier est le **jumeau** : une simple copie markdown du document, posée dans votre dossier de projet, à vous de la modifier comme n'importe quoi d'autre. La créer ne modifie jamais l'original.

Dans l'arborescence de fichiers, vous voyez toujours une seule ligne — `memo.docx`. Le jumeau, le dossier d'images extraites du document (`memo.docx.assets/`), et un petit fichier caché enregistrant ce qui a été converti depuis quoi sont tous repliés dans cette ligne unique, si bien que votre projet continue de ressembler à ce qu'il est dans Finder. Cliquez sur la ligne et le jumeau s'ouvre en mode lecture/édition (section 6) avec tout ce que ce mode offre : deux faces, ⌘S, la protection contre la perte — et, une fois en plein cadre, les surlignages.

Deux conséquences à connaître. Le nommage ne peut pas entrer en collision : un `memo.md` que vous avez écrit vous-même est un fichier différent de `memo.docx.md`, et enough ne les confond jamais. Et si vous supprimez `memo.docx` dans Finder, rien ne casse — le jumeau devient discrètement un fichier markdown ordinaire dans votre arborescence, ce qu'il a toujours été de toute façon.

Vos readvisors voient la même chose que vous. Demandez que `report.pdf` soit lu et ils obtiennent le jumeau, en en convertissant un d'abord s'il n'y en a pas encore ; demandez que quelque chose soit changé et ils modifient le jumeau, exactement là où vont vos propres modifications.

### 7.2 Ce qu'enough peut ouvrir de cette façon

Cette liste vient de l'application elle-même plutôt que d'un texte que quelqu'un doit penser à mettre à jour — si vous lisez ceci en dehors d'enough, ouvrez le centre d'aide dans l'application (section 10) pour la voir remplie :

{{convert-formats}}

### 7.3 Le badge dans l'arborescence

Chaque document convertible porte un petit badge au bord droit de sa ligne, et ce badge a exactement un travail : vous dire si les deux moitiés sont toujours d'accord.

- **Discret** — converti, et les deux côtés correspondent. Rien à faire.
- **Allumé, dans votre couleur** — vous avez modifié le jumeau. Ces changements sont dans le markdown et pas encore dans l'original ; exportez quand vous êtes prêt (section 7.5).
- **Allumé, dans la couleur de votre readvisor** — l'original a changé hors d'enough depuis sa conversion. Quelqu'un l'a modifié dans Word ; une nouvelle copie a atterri par-dessus ; il est arrivé depuis un disque partagé.
- **Allumé, dans la couleur d'erreur** — les deux à la fois. C'est le seul cas où enough vous pose la question, et il la pose (section 7.7).
- **Creux** — convertible, pas encore converti. Cliquez dessus et il se convertit.
- **Creux, et cliquer explique un extra** — un PDF, une présentation, ou un classeur sur une installation qui ne sait pas encore les lire (section 7.8).

Survolez le badge pour la même chose en une phrase. Cliquer sur le badge fait exactement ce que fait cliquer sur le nom du fichier.

### 7.4 La première fois que vous en ouvrez un

La première fois que vous ouvrez chaque *type* de document, une courte modale explique ce qui va se passer — ce qu'est un jumeau, où il va, que l'original reste en place. Un seul bouton OK. C'est une fois par type, pas une fois par fichier : votre deuxième document Word s'ouvre simplement.

La conversion d'un document bureautique est rapide, bien en dessous d'une seconde pour tout ce qui est typique. Vous verrez un petit toast dans le coin pendant qu'elle tourne, avec un bouton **annuler** sur les plus lentes. Les PDF prennent plus de temps et ont droit à une barre de progression honnête (section 7.8).

### 7.5 Exporter vos changements en retour

Un jumeau ouvert porte un bouton **exporter** dans son habillage. Une modale, trois décisions :

**Quel format.** Le format propre à l'original est présélectionné, et le reste des cibles d'export est là aussi — un document Word peut sortir en PDF, en EPUB, ou en page HTML autonome. Tout ce que le format ne peut pas faire s'affiche grisé avec la raison, jamais silencieusement absent.

**Une copie, ou l'original.** Le défaut est une **copie datée** écrite à côté de l'original — `memo-2026-08-19-1042.docx` — et le nom de fichier exact est prévisualisé dans la modale avant que vous ne validiez. Rien n'est en jeu : vous obtenez un nouveau fichier, l'ancien n'est pas touché. La seconde option écrase l'original sur place, et elle n'est proposée que quand le format vers lequel vous exportez est celui de l'original. Choisissez-la et enough vous propose une **annulation** ensuite : garder le nouveau fichier, ou remettre les anciens octets, octet pour octet.

**Si vous voulez le garder synchronisé** à partir de maintenant — section 7.6.

Un mot sur ce qui survit au voyage. Écraser un `.docx` ou un `.odt` utilise l'original comme référence de style, donc la taille de page, les polices, et les éventuels en-têtes et pieds de page courants reviennent avec votre texte — des choses que markdown n'a aucun moyen d'exprimer et qui seraient sinon perdues. Ce que markdown ne peut vraiment pas transporter ne revient pas : suivi des modifications et commentaires (acceptés puis abandonnés à l'entrée), zones de texte, champs, dimensionnement précis des images. Cette asymétrie explique pourquoi la copie datée est le défaut, et pourquoi enough ne réécrit jamais un original de sa propre initiative.

### 7.6 Garder l'original synchronisé

Cochez **garder l'original synchronisé** dans la modale d'export et chaque enregistrement du jumeau réécrit discrètement l'original aussi. Modifiez dans enough, et le `.docx` sur votre disque est à jour dès qu'un collègue le demande. C'est un réglage par fichier, il s'applique dès l'instant où vous le cochez, et une petite confirmation apparaît chaque fois qu'un enregistrement se propage.

C'est proposé pour les formats qui peuvent être réécrits — Word, OpenDocument, Rich Text, EPUB ; la colonne « garder synchronisé » de la section 7.2 fait autorité. Les PDF ne peuvent pas participer, et la raison mérite d'être dite clairement : enough peut *écrire* un PDF à partir de markdown, mais il recompose le document depuis zéro. Un PDF synchronisé remplacerait votre original soigneusement mis en page par une simple recomposition de ses mots, à chaque enregistrement. Ce n'est pas une synchronisation, c'est une démolition, donc ce n'est pas proposé.

### 7.7 Quand les deux côtés ont changé

L'original peut évoluer sans vous. Vous modifiez le jumeau ici ; quelqu'un modifie le `.docx` dans Word ; il y a maintenant deux versions de la vérité.

enough le remarque. Il compare l'original à ce qu'il avait enregistré au moment de la conversion, à chaque instant qui compte — quand l'arborescence est dessinée, quand vous ouvrez le document, quand vous enregistrez, quand vous exportez — et un fichier simplement *touché* (copié, sauvegardé, ouvert puis fermé) ne compte pas : la vérification lit le contenu, pas seulement les horodatages.

Quand les deux côtés ont vraiment changé, vous obtenez une modale avec trois choix en mots simples :

- **Garder mon jumeau.** Rien n'est écrit. Le badge revient à « vous l'avez modifié » et vous déciderez plus tard.
- **Exporter par-dessus l'original.** Votre markdown l'emporte ; l'original est réécrit, avec une annulation proposée comme d'habitude.
- **Reconvertir depuis l'original.** L'original l'emporte ; un nouveau jumeau est écrit — et votre ancien jumeau est mis de côté comme fichier d'annulation plutôt que supprimé.

Aucun choix dans cette modale ne détruit quelque chose que vous ne pouvez pas récupérer. C'est la règle de conception sur laquelle toute la fonctionnalité est construite.

### 7.8 Lire des PDF, présentations, et classeurs : l'extra PDF

Lire un PDF est un problème plus dur que lire un fichier Word. Un `.docx` sait encore ce qu'est un titre ; un PDF sait seulement où l'encre est allée, et en extraire un tableau, une mise en page à deux colonnes, ou un scan demande de vrais modèles de document. Ces modèles sont volumineux, donc ils ne sont pas dans l'installation de base — ils sont à un clic de distance à la place : **⚙ fenêtre UI → extras → installer l'extra PDF**.

Ce que ça coûte, honnêtement :

- environ **250 Mo à télécharger**, et environ **1 Go sur le disque** une fois installé ;
- plus environ **0,7 Go de poids de modèle**, récupérés une fois et gardés dans `~/enough/weights/docling/` ;
- quelques minutes, en majorité du téléchargement. L'installeur diffuse son journal dans la fenêtre pour que vous puissiez regarder, et les moteurs s'activent en direct — aucun redémarrage.

Ce que vous obtenez : les **PDF**, scans compris (le texte est lu dans les pixels par OCR) ; les **présentations PowerPoint**, dont les diapositives deviennent des sections titrées ; et les **classeurs Excel**, dont les feuilles deviennent des tableaux markdown.

La vitesse, mesurée plutôt que devinée, sur silicium Apple : environ **0,9 seconde par page** pour un PDF numérique, plus un chargement de modèle ponctuel d'environ **10 secondes** par conversion. Donc un PDF d'une page prend environ dix secondes, un livre de cent pages environ une minute et demie, et une présentation ou un classeur quelques secondes. Les conversions longues affichent une progression et peuvent être annulées ; annuler ne laisse rien derrière soi — pas de jumeau à moitié écrit, pas de dossiers égarés.

Deux choses vous épargneront un moment de perplexité plus tard. D'abord : **écrire des PDF n'a besoin de rien de tout ça.** N'importe quel jumeau exporte vers PDF sur toute installation, extra ou pas, parce que le compositeur qui s'en charge est fourni avec enough. L'extra sert à *lire*. Ensuite : si le message « nécessite un extra » apparaît sur une machine où vous êtes sûr de l'avoir installé, relisez quelle phrase exacte vous avez reçue — les paquets et les poids de modèle sont deux téléchargements séparés, et une connexion coupée en cours de récupération peut vous laisser avec le premier mais pas le second. Relancer l'installation termine le travail et ne retélécharge rien que vous avez déjà.

Les mises à jour gardent l'extra. `update-enough.command` (et `/update-enough`) se souviennent de ce que vous avez installé et le redemandent à chaque synchronisation, donc une mise à jour de routine ne vous retire jamais discrètement la lecture de PDF.

### 7.9 Images, et regarder l'original

Cliquez sur une image et elle s'ouvre dans une visionneuse simple : ajustée à la largeur par défaut, cliquez pour passer à la taille réelle et faire défiler autour, un damier derrière tout ce qui est transparent, et le nom, les dimensions en pixels, et la taille du fichier dans l'en-tête. C'est en lecture seule. enough n'est pas un éditeur d'image et n'a aucune ambition dans ce domaine.

Les images *à l'intérieur* d'un document, c'est une autre affaire, et elles passent bien : la photo de votre fichier Word est extraite dans `memo.docx.assets/` et s'affiche dans la face lecture du jumeau exactement comme n'importe quelle autre image markdown.

Et quand le jumeau ne suffit pas, l'habillage d'un PDF porte **voir l'original** : ça ouvre le vrai PDF dans le panneau, pour que vous puissiez vérifier le jumeau par rapport à la vraie page. Fermez-le et vous êtes de retour dans le jumeau, là où vous l'aviez laissé.

### 7.10 Ce que la conversion vous coûte, en deux phrases

Deux limites méritent d'être nommées à voix haute plutôt que de vous laisser les découvrir. Les feuilles d'un classeur arrivent comme des tableaux mis bout à bout **sans titres de nom de feuille** — le lecteur ne les émet pas, et enough préfère laisser un vide plutôt qu'inventer une étiquette. Et une image extraite d'un PDF reçoit le texte alternatif « Image », à chaque fois : il n'y a pas de légende dans le fichier pour lui en donner une meilleure.

Au-delà de ça, la promesse permanente : **vos originaux ne sont jamais modifiés sauf si vous le demandez.** Convertir ne fait jamais qu'écrire de nouveaux fichiers à côté d'eux. Exporter-écraser est le seul chemin qui touche un original, ça demande un clic délibéré, et ça vous laisse une annulation.

---

## 8. Le dossier de projet et `rness/`

Un projet est un dossier. N'importe quel dossier. enough y ajoute exactement une chose : `rness/`, le cerveau externalisé de ce projet. Tout ce que vos readvisors sont, savent, et retiennent ici vit dans ce dossier sous forme de fichiers ordinaires. Vous pouvez tout lire, tout modifier, et le mettre sous git si c'est votre habitude.

L'agencement :

```
your-project/
  rness/
    AGENT.md            who your chief readvisor is    (5.3)
    MOTIVATION.md       why they work                  (5.3)
    active-paradigm     which paradigm is in force     (16)
    paradigms/          available reasoning frameworks (16)
    skills/             available skills               (19)
    readvisors/         the readvisors you can turn on (17)
    policies/           the hard rules                 (5.4)
    composure-forms/    composure forms you saved      (4.5)
    knowledge/          project memory                 (8.1)
      councils/         exported council transcripts   (18)
    io/                 input/output workspace          (8.2)
      composure/        where new composures land       (4.7)
    requests/           long-running work tracking      (8.3)
  ...your actual files...
```

Deux de ces dossiers n'arrivent que quand vous en avez besoin : `composure-forms/` la première fois que vous enregistrez une composure comme form, `knowledge/councils/` la première fois qu'un conseil conclut. Un dossier vide qui ne s'explique jamais est un dossier sur lequel vous finissez par poser des questions.

**Si ce projet est antérieur à la 0.3.5**, il porte un dossier `rness/roles/` plutôt que `rness/readvisors/`. enough le renomme la prochaine fois que vous ouvrez le projet, en un seul geste, en transportant intacts vos readvisors locaux au projet et vos réglages activé/désactivé. S'il n'y arrive pas — disque en lecture seule, dossier que quelque chose d'autre tient — rien ne casse : tout continue de fonctionner sous l'ancien nom, et le renommage est retenté au lancement suivant.

Les entrées liées par symlink (en italique dans l'arborescence) suivent les défauts globaux ; personnalisez n'importe laquelle d'entre elles pour en forker une copie locale (section 3.1). Les fichiers que vous déposez dans le projet par n'importe quel moyen — Finder, un autre éditeur, un readvisor — sont également visibles pour tout le monde au tour suivant.

Un document converti (section 7) ajoute lui aussi des fichiers ici, toujours à côté de l'original et toujours nommés d'après lui : `memo.docx` obtient un jumeau à `memo.docx.md`, ses images dans `memo.docx.assets/`, et un `.memo.docx.convert.json` caché qui enregistre ce qui a été converti depuis quoi et quand. L'arborescence replie les trois dans la ligne de l'original, mais ce sont des fichiers ordinaires sur votre disque — vous pouvez copier la paire vers une autre machine, la mettre sous git, ou supprimer le jumeau et recliquer sur l'original pour en obtenir un tout frais. Le manifeste caché est la comptabilité d'enough ; laissez-le tranquille et il reste exact. Supprimez-le et enough traite simplement le document comme jamais converti.

### 8.1 Le dossier knowledge

`rness/knowledge/` est la mémoire propre à chaque projet.

**`project-profile.md`** est le fichier le plus utile du dossier. Son contenu est injecté dans le prompt système à chaque tour : tout ce qui est écrit ici est dans la mémoire de travail de votre readvisor en chef, sans recherche nécessaire. Il le tient à jour au fil de votre travail — préférences observées, fichiers et personnes récurrents, conventions que vous avez adoptées, fils laissés ouverts — et vous pouvez le modifier directement. Énoncez une préférence permanente une fois dans le profil plutôt que de la répéter à chaque séance. La politique profile-maintenance garde le fichier discipliné : des observations concrètes plutôt que des étiquettes vagues, de la distillation plutôt que de l'archive.

**`session-logs/`** contient un journal markdown daté des tours de chaque session, plus le journal du broker (section 9). Un historique en ajout seul. Parcourez-le, ou grep-ez-le, quand vous devez reconstituer ce qui s'est passé mardi dernier.

Au-delà de ces deux-là, le dossier est à vous. Ajoutez un sous-dossier `glossary/`, un fichier de leçons apprises, des notes de contexte — vos readvisors peuvent consulter tout ce que vous mettez ici.

### 8.2 Le dossier io

`rness/io/` est l'espace de travail de passage :

- **`input/`** — déposez des fichiers ici pour qu'ils soient traités. Les pages web récupérées atterrissent aussi ici automatiquement, converties en markdown et mises en cache, si bien qu'une page récupérée une fois reste ancrée pour toujours.
- **`output/`** — là où atterrissent les artefacts générés. Passez en revue, gardez ce qui est bon, videz le reste.
- **`cloud-cache/`** — si vous utilisez l'emplacement de modèle cloud, chaque échange cloud est enregistré ici (section 15.2). Même le travail dans le cloud laisse une trace papier locale et grep-able.

### 8.3 Requêtes : comment les travaux longs survivent

Celle-ci figure rarement dans les visites express de démarrage, mais c'est le mécanisme qui rend possible le travail sur plusieurs sessions, alors ça vaut deux minutes.

Quand vous demandez quelque chose qui prendra plus d'un tour ou deux, un **fichier de requête** s'ouvre dans `rness/requests/` : un enregistrement markdown de l'objectif, des points de contrôle de progression, et des décisions prises en chemin. Vous n'avez pas à le demander. Reconnaître la forme d'une tâche, c'est le travail de votre readvisor en chef.

Le fichier de requête compte parce que les fenêtres de contexte se remplissent. enough surveille la pression conversationnelle, et — selon la politique context-management — votre readvisor en chef enregistre son état dans le fichier de requête actif avant que ça déborde. Selon votre réglage d'orchestrateur, enough se remet ensuite automatiquement à zéro (effaçant la conversation en mémoire et reprenant à neuf depuis le point de contrôle) ou fait une pause avec une bannière pour que vous remettiez à zéro quand vous êtes prêt. Dans tous les cas, c'est le système de fichiers qui est la vraie mémoire, pas la conversation : une session neuve lit le bloc Continuation du fichier de requête et reprend là où les choses en étaient.

Les requêtes terminées se déplacent vers `rness/requests/done/` — cliquez sur **marquer comme terminé** sur une requête ouverte, ou dites-le dans le panneau. Le dossier done est protégé en écriture vis-à-vis de vos readvisors, et il fait aussi office de journal honnête de tout ce que vous avez réellement livré tous les deux.

---


## 9. La fenêtre broker

Le broker est l'ancre de confiance d'enough. Chaque appel d'outil que font vos readvisors — chaque lecture de fichier, écriture de fichier, commande shell, et récupération web — passe par lui. La fenêtre broker 🔀 est l'endroit où vous observez et ajustez tout ça.

Treize interrupteurs, en groupes :

| Interrupteur | Ce qu'il contrôle |
|---|---|
| trace log | Si le broker écrit ou non son journal |
| local models only | Si l'emplacement cloud (OPRO-API) est seulement proposé dans le sélecteur de modèle |
| read_file / write_file / shell brokered | Journalisation de trace par outil, un interrupteur chacun — trois en tout (les listes blanches sont *toujours* appliquées quoi qu'il arrive) |
| fetch_url enabled | Si l'outil de récupération web fonctionne du tout |
| Tor for off-list fetches | Domaines hors liste blanche : router via Tor (activé) ou refuser (désactivé) |
| cache & convert fetches | Convertir les pages récupérées en markdown et les mettre en cache dans `rness/io/input/` |
| wikisink tools | Si les quatre outils wiki de vos readvisors fonctionnent (votre propre navigation 🚰 n'est jamais soumise à contrôle) |
| wikisink live updates | Si les passes de mise à jour peuvent contacter Wikipédia du tout (désactivé = rapport depuis l'état local uniquement) |
| cacheawl tools | Si les outils de cachebox de vos readvisors fonctionnent (votre propre mode cacheawl n'est jamais soumis à contrôle) |
| composure tools | Si vos readvisors peuvent lire et modifier des composures (votre propre canevas n'est jamais soumis à contrôle — section 4.9) |
| forge new readvisors | Si la compétence `readvisory` peut installer pour vous un readvisor terminé (section 19.6). Désactivé, l'entretien et la rédaction ont quand même lieu, et le classement vous revient |

L'en-tête de la fenêtre porte aussi le seul bouton d'enough qui change le nom de quelqu'un : **renommer votre readvisor en chef**. Il ouvre un petit champ, accepte de un à vingt-quatre caractères, et le nouveau nom est dans la signature de la prochaine chose que dit votre chef. C'est un réglage à l'échelle de la machine, comme le thème — un chef, un nom, partout. Il n'a pas d'historique : la signature est toujours le nom actuel, parce qu'un renommage qui remonterait dans votre transcription se lirait comme deux personnes différentes présentes dans la pièce.

Tout est activé par défaut : les défauts font confiance à vos readvisors avec le projet et les gardent honnêtes grâce à une trace papier. Cette trace — le **journal de trace** — atterrit dans `rness/knowledge/session-logs/<date>-broker.md` : horodatage, outil, décision, arguments, résultat, pour chaque appel passé par le broker. Et quand un interrupteur ou une liste blanche bloque quelque chose, le readvisor reçoit un message de refus clair disant ce qui a été bloqué et pourquoi, pour qu'il puisse vous le dire plutôt que d'échouer en silence.

Remarquez le principe de conception dans ce tableau : les interrupteurs qui contrôlent les outils de vos readvisors ne contrôlent jamais *votre* interface. Désactiver cacheawl tools ne vous exclut pas du mode cacheawl. Ça veut dire que rien ne peut aller puiser dans le dépôt en votre nom.

---


## 10. La fenêtre UI et les docs d'aide

Le bouton UI ⚙ ouvre les préférences d'affichage et le matériel de référence. Un petit bouton **aide** se trouve en haut à droite de cette fenêtre, à côté du × : il ouvre ce manuel en lecture seule, dans l'application, comme un mode plein cadre comme les autres (section 14). À côté se trouve **dictionnaire**, qui ouvre FEED, le dictionnaire anglais d'enough (section 13).

**Lire le manuel.** La barre d'outils du manuel a un bouton **sommaire** : la liste de chaque section et sous-section numérotée, à côté du texte quand il y a la place et repliée quand il n'y en a pas (dans la taille étroite en panneau latéral, par exemple), avec la section que vous lisez marquée au fil du défilement. **chercher**, ou ⌘F quand le manuel est au premier plan, ouvre une barre de recherche : chaque occurrence est marquée sur place avec un compte à côté du champ, Entrée et maj-Entrée les parcourent, et Esc la ferme. Et partout où ce manuel dit « section 7.3 », ces mots sont un lien qui vous y emmène. Chaque saut — un clic dans le sommaire, un lien de section, une recherche qui vous a emporté loin — laisse derrière lui une petite pastille **↩ retour à l'endroit où vous étiez**, et un clic vous remet là où vous lisiez.

La sortie voyage désormais sur la barre de titre : **fermer le projet → accueil**, là-haut à côté du bouton aide, qui met fin à cette session et vous ramène à l'écran d'accueil (section 2.5). Elle demande avant de le faire, et elle précise ce qu'elle ne fait pas — le dossier sur le disque n'est pas touché. Dans l'application, vous auriez plus probablement recours à ⌘W ; ce bouton, c'est la même chose, et c'est le *seul* moyen si vous faites tourner enough dans un navigateur. (Il n'est pas là sur l'écran d'accueil lui-même, où il n'y a pas de projet à fermer.)

Elle contient aussi la seule chose dans enough que vous pouvez installer depuis l'intérieur d'enough : la ligne **extras** pour la **lecture de PDF** (section 7.8). La ligne dit où vous en êtes — non installé, en cours d'installation, installé, ou installé mais pas terminé — et le bouton d'installation diffuse tout son journal dans la fenêtre pendant qu'il tourne, si bien qu'un long téléchargement devient quelque chose que vous pouvez regarder plutôt que quelque chose que vous subissez. Une fois terminé, les PDF commencent à s'ouvrir ; rien n'a besoin de redémarrer.

### 10.1 Thèmes

Quatre sont fournis avec enough : **Enough Default** (violet-bleu profond et sombre), **Pastel** (papier pâle, dans l'esprit du thème « Man Page » du Terminal), **Wireframe**, et **Darknest**. Le changement est instantané, et chaque icône de l'interface redérive sa variante claire ou sombre à la volée.

Les thèmes ne sont pas codés en dur. Ils vivent dans `~/enough/config/ui.json` comme des blocs nommés de valeurs de couleur, chacun appliqué comme une propriété CSS personnalisée. Copiez un bloc existant, renommez-le, changez les couleurs, rechargez : votre thème est dans le menu déroulant. Le bloc `_doc` en tête du fichier explique chaque clé.

### 10.2 Polices

Même motif. Quatre familles fournies — SF Mono, sans-serif système, Georgia serif, Courier — et vos propres ajouts sont bienvenus dans le même `ui.json`. Pour la taille, voyez les deux molettes ci-dessous (section 10.3) — et dans un onglet de navigateur, le bon vieux zoom du navigateur (⌘+ / ⌘−) fonctionne toujours très bien par-dessus.

### 10.3 Dimensionnement — échelle de l'ui et échelle du texte

Le zoom du navigateur avait toujours été la réponse ici, jusqu'à ce que l'application de bureau arrive sans navigateur enroulé autour d'elle. Alors enough s'est développé le sien, et en a profité pour faire encore mieux : deux molettes au lieu d'une, sur la ligne sous le thème.

**l'échelle de l'ui** redimensionne *tout* — icônes, étiquettes, barre latérale, discussion, cette fenêtre même — par pas de 0,1×. **l'échelle du texte** redimensionne seulement le document devant vous : la page en lecture/édition, un article wikisink, l'aperçu de fichier, ce manuel en mode référence. Elles se multiplient, et elles ne se gênent pas : une interface à 0,9× autour d'un texte à 1,5× est une très bonne façon de lire un manuscrit, et l'inverse est une très bonne façon d'en réduire un pour qu'il ne gêne pas votre après-midi. Cliquez sur l'un ou l'autre chiffre pour ramener cette molette à 1,0× et laisser l'autre tranquille.

Les deux sont mémorisées **par dossier de projet** — le manuscrit que vous lisez depuis l'autre bout de la pièce et les notes que vous gardez sur le bureau ont chacun leur propre taille, et ni l'une ni l'autre n'entraîne l'autre avec elle. L'écran d'accueil reste à la taille normale, donc les molettes n'y apparaissent pas.

Les limites respirent avec votre écran : environ 0,5× à 2× sur les écrans d'aujourd'hui, se resserrant sur une petite fenêtre pour que l'interface garde toujours assez de place pour être elle-même, se desserrant sur des écrans très grands et très denses (le mur 8K de 2046 a droit à 3×). Quand un pas franchirait la limite, le bouton frétille, le chiffre pulse en rouge, et rien ne change — c'est tout le message d'erreur.

### 10.4 Langues

L'interface parle six langues : anglais, français, espagnol, allemand, chinois, et japonais. Le menu déroulant **langue de l'interface** sur la même ligne change tout ce que vous regardez — étiquettes, infobulles, bulles `(?)`, ce manuel — en direct, sans redémarrage. Le choix est global à la machine, voyageant dans `ui.json` comme le thème, donc l'accueil et chaque projet sont d'accord là-dessus.

Ce qu'elle ne touche délibérément *pas* : vos fichiers, votre discussion, vos readvisors. Parlez-leur dans la langue qui vous convient — les modèles locaux sont à l'aise dans ces six langues — mais enough garde son propre échafaudage (compétences, paradigmes, prompts, fichiers de projet) en anglais, parce que c'est la langue que les modèles lisent le plus fidèlement. Quelques éléments générés restent en anglais aussi — les listes tirées en direct de ce qui est installé sur *votre* machine, comme les compétences dans une bulle ou le tableau des formats de fichier. Et partout où une traduction n'a pas encore rattrapé une nouvelle étiquette anglaise, vous verrez l'anglais plutôt qu'un vide : moins joli, jamais cassé. Vous en repérez une ? C'est un bug — [enough.support](https://enough.support) l'accueille volontiers.

### 10.5 Aide-mémoires

Deux colonnes de référence, juste dans la fenêtre UI.

**Raccourcis clavier :**

| Touches | Action |
|---|---|
| esc | ferme le mode ouvert le plus au-dessus |
| ⌘ \ | affiche / masque la barre latérale |
| ⌘ / | affiche / masque le panneau readvisor |
| ⇧ ⌘ / | donne toute la fenêtre au panneau readvisor |
| ⌘ K | place le curseur dans le champ de discussion |
| ⌘ Enter | envoie le message |
| shift Enter | saut de ligne au lieu d'envoyer |
| ⌘ B / I / U | gras / italique / souligné sur la sélection (face lecture) |
| ⌘ S | enregistrer (face édition) |
| ⌥ clic | menu contextuel de l'arborescence |
| ⇧ ⌘ D | entrée du dictionnaire pour le mot sélectionné, ou le mot sous le curseur |
| clic droit sur un mot | menu de l'entrée du dictionnaire (maintenez maj pour le menu système) |

(Sur un clavier non-Mac : Ctrl pour ⌘, Alt pour ⌥.)

Ce sont les raccourcis que l'interface elle-même gère, donc ils fonctionnent aussi bien dans l'application que dans un onglet de navigateur. L'application en ajoute deux siens, depuis la barre de menus : **⌘W** ferme le projet et vous ramène à l'écran d'accueil (section 2.5) — il ne ferme *plus* la fenêtre — et **⌘Q** quitte, comme il l'a toujours fait.

**L'aide-mémoire markdown :** titres, listes, liens, code, citations — toute la référence rapide, pour quiconque est encore en train de devenir couramment bilingue en markdown. Ce qui vaut la peine, puisqu'enough le parle nativement partout.

### 10.6 Aide intégrée (IHH)

Les bulles `(?)` disséminées dans l'interface sont le système d'aide intégré : une bulle par concept — compétences, readvisors, le panneau readvisor, le sélecteur de paradigme, la composure avec ses modules et ses outils, le journal, rness, io, knowledge, cacheawl, wikisink, le système de modes, les documents convertis, et ainsi de suite — chacune avec un **what**, un **how**, et une liste **ideas**. Les bulles compétences, readvisors, et paradigmes listent ce qui est réellement installé dans *votre* projet, et la bulle document-converti tire son tableau de types de fichiers du registre de formats propre à l'application — tout généré en direct, si bien que l'aide ne dérive jamais de la réalité. (Le même tableau apparaît à la section 7.2 de ce manuel, depuis la même source.)

Les bulles sont contrôlées par dossier de projet via la case à cocher « bulles d'aide (?) » dans la fenêtre UI. Activée par défaut pour un nouveau dossier, et le réglage colle par dossier — donc votre projet chevronné du quotidien peut se faire discret pendant qu'une expérience toute fraîche garde ses petites roues.

Même l'aide est personnalisable. Le contenu vit dans un seul fichier markdown (`enough/static/help-docs.md`) ; le modifier modifie les bulles.

---

## 11. Wikisink

Wikisink (🚰) met une copie hors ligne de Wikipédia anglais sur votre machine : consultable dans l'application, cherchable en texte intégral, lisible par vos readvisors, annotable, et rafraîchissable à la demande avec un rapport de changements. Une fois configuré, il n'a besoin d'aucun internet du tout.

### 11.1 Configuration

Cliquez sur 🚰 pour la première fois et l'assistant demande trois choses.

1. **Taille.** Les archives sont des builds Kiwix, texte seul sauf mention contraire :

   | variante | contenu | taille approx. |
   |---|---|---|
   | top 1 M articles *(défaut)* | le million les plus lus | ~16 Go |
   | tout Wikipédia anglais | chaque article | ~49 Go |
   | top 50k | les cinquante mille les plus lus | ~2,1 Go |
   | top 50k mini | top ~50k, sections d'intro seulement | ~320 Mo |
   | Simple English | Simple Wikipedia complet | ~950 Mo |

2. **Stockage.** Le défaut est `~/enough/wikisink` ; n'importe quel dossier convient, disques externes compris. Laissez environ 5 % de marge au-delà de la taille de l'archive.
3. **Confirmation.** Le téléchargement est reprenable et survit aux fermetures — pause, reprise, ou annulation depuis la même fenêtre pendant que le reste d'enough continue de fonctionner.

L'archive est un unique fichier `.zim` lu sur place. Il n'est jamais extrait, et il n'encombre jamais votre gestionnaire de fichiers. Vous pouvez enregistrer **plusieurs installations** — disons, l'archive complète sur un disque externe plus une petite sur le disque interne — et basculer entre elles dans la liste des installations ⚙. Un disque débranché ne casse rien : cette installation s'affiche comme inaccessible jusqu'au retour du disque, et vos commentaires et dérogations vivent indépendamment de toute archive particulière.

Une fois installé, 🚰 ouvre le lecteur : précédent et suivant, des suggestions de titre en direct dans le champ de recherche (Entrée lance une recherche en texte intégral sur toute l'archive), un dé à article aléatoire 🎲, et un badge de source qui vous dit si vous lisez l'instantané de l'archive (`ZIM <date>`), une copie plus fraîche issue d'une passe de mise à jour (`en direct <date>`), ou une copie préservée (`préservé`). Les liens internes restent dans l'application ; les liens externes s'ouvrent dans votre navigateur. Sélectionnez un passage et il apparaît comme une pastille au-dessus de la zone de message dans le panneau readvisor, prêt à partir avec votre prochain message (section 5.2).

**La pastille de nouvel instantané.** Kiwix reconstruit ces archives périodiquement, et vous ne devriez pas avoir à aller le chercher. Quand une version plus récente de *votre* variante existe, une petite pastille apparaît dans la barre d'outils du lecteur — `nouvel instantané : <date> · <taille>`. Cliquez dessus, confirmez la taille, et la mise à niveau s'exécute sur place : même dossier de stockage, téléchargée d'abord et substituée seulement une fois terminée, l'ancien fichier supprimé après coup et pas avant. Vos commentaires, enregistrements, et dérogations 🛡 traversent intacts, parce qu'aucun d'eux ne vit à l'intérieur de l'archive. La pastille devient l'indicateur de progression pendant le téléchargement, puis disparaît. enough vérifie ça au plus une fois par jour, jamais pendant que le lecteur affiche quelque chose, et reste silencieux quand vous êtes hors ligne — ce qui est l'état normal d'une fonctionnalité Wikipédia hors ligne. La même mise à niveau est disponible par le chemin long, dans la liste des installations ⚙, et les passes wikisink le signalent aussi (section 11.3) — mais appuyer sur le bouton reste toujours votre décision.

### 11.2 Enregistrer et verrouiller des articles

**Enregistrer.** Le bouton enregistrer propose deux destinations : le dossier `wiki/` de ce projet, ou le cachebox wiki global à la machine (`~/enough/cacheawl/wiki/`) partagé par tous les projets. Dans les deux cas, un enregistrement est un dossier — `article.html`, l'article octet pour octet tel que l'archive l'avait, plus `_manifest.md` portant le titre, l'url source, la date de récupération, et la ligne de licence CC BY-SA. Chaque article enregistré est autodescriptif, ce qui veut dire que si son texte finit un jour dans quelque chose que vous publiez, l'attribution dont vous avez besoin est déjà posée juste à côté. Cliquez sur un `article.html` enregistré dans l'arborescence et il s'ouvre dans le lecteur en fidélité complète — infobox, tableaux, tout — même quand aucune archive n'est accessible. Pour désenregistrer, survolez le dossier enregistré dans l'arborescence et cliquez sur le 🗑 qui apparaît.

Enregistrer, c'est pour *vous* : des copies hors-ligne-de-l'hors-ligne, l'attribution pour publication. Vos readvisors n'ont pas besoin des enregistrements — leurs outils lisent n'importe quel article de l'archive en texte propre à la demande.

**Commentaires.** Sélectionnez du texte et appuyez sur 💬, ou utilisez le 💬 de la barre d'outils pour une note au niveau du paragraphe. Les fils vivent dans le panneau 🗨 : répondre, résoudre, rouvrir, sauter. Les commentaires s'attachent à l'*article*, pas à un fichier, et ils survivent aux mises à jour d'article en se dégradant en douceur. Le texte encore présent reste **ancré**. Le texte retiré par une édition est **repositionné** sur son paragraphe. Un paragraphe purement supprimé laisse le commentaire **orphelin** dans le panneau — étiqueté, mais jamais supprimé automatiquement.

**Verrouillage (dérogations de suppression).** Il arrive que Wikipédia en direct supprime un article dont vous dépendiez ; le cas classique est un sujet de niche coupé pour « notoriété » plutôt que pour sa qualité. Le bouton 🛡 préserve votre copie locale pour toujours — servie dès lors avec un badge `préservé`, exclue des futurs rafraîchissements, toujours cherchable. Les rapports de passe de mise à jour notent en fait les suppressions détectées (les justifications à la « notoriété » sont notées suspectes ; celles pour violation de droit d'auteur sont notées bénignes), pour que vous sachiez quelles suppressions méritent un coup d'œil. Et déroger reste délibérément votre décision à vous seul : un readvisor peut recommander 🛡, mais il ne peut jamais l'appuyer.

### 11.3 La mise à jour wikisink, avec rapport de changements

« Wikisink » est aussi un verbe. Chaque article que vous avez enregistré ou commenté est *surveillé*, et demander à votre readvisor de « lancer un wikisink » (ou le laisser saisir l'outil `wikisink`) vérifie l'ensemble surveillé par rapport à Wikipédia en direct et fait un rapport. Une passe :

1. rafraîchit les articles surveillés qui ont changé dans une surcouche locale (leur badge bascule vers `en direct`) ;
2. signale les **pics d'édition** — des articles surveillés soudainement édités des dizaines de fois par jour, plus des candidats à la poussée à l'échelle de tout Wikipédia ;
3. compare le **classement quotidien des 1000 articles les plus vus** à la dernière passe : ceux qui montent, ceux qui descendent, les nouvelles entrées, les sorties, et les tendances de vues pour vos articles surveillés ;
4. vérifie les **suppressions** d'articles surveillés ou récemment vus, notées pour leur degré de suspicion (section 11.2) ;
5. note quand un **nouvel instantané de base** est disponible. Remplacer l'archive de base de plusieurs Go reste toujours votre décision — appuyez sur la pastille dans la barre d'outils du lecteur (section 11.1) ou utilisez la liste des installations ⚙. Il n'existe aucun outil qui la substitue.

Le rapport arrive dans la discussion en markdown ; la version complète sans plafond est gardée sous le dossier d'état de wikisink. Les passes sont polies envers Wikipédia — groupées par lots, User-Agent honnête — et reprenables si interrompues, et une passe `report-only` saute l'étape de rafraîchissement. Deux interrupteurs du broker gouvernent tout ça : l'un contrôle entièrement les outils wiki de vos readvisors, l'autre peut forcer les passes entièrement hors ligne.

---

## 12. Cacheawl

Cacheawl est le dépôt de texte global à la machine : l'endroit pour les choses que vous voulez garder pour toujours et atteindre depuis chaque projet. Il vit dans `~/enough/cacheawl/`, caché de l'arborescence de chaque projet, partagé entre toutes vos instances d'enough. (Si vous faisiez tourner une version antérieure d'enough, votre ancienne bibliothèque `infoworld/` a été dissoute dans cacheawl au premier lancement de la 0.1.6 — `personal/`, `public/`, et `wiki/` sont devenus vos trois premiers cacheboxes. Rien n'a été perdu.)

### 12.1 Les cacheboxes et leurs cartes merirmaid

Un **cachebox** est un dossier de premier niveau dans le dépôt, et il existe en deux variantes. Les **box simples** contiennent du texte gardé pour toujours que vous organisez vous-même : une box `personal` de notes de référence, une box `press` de textes publiés, n'importe quelle structure qui vous sert. Les **répliques mises en cache** sont des box *ingérées* depuis une source — un dossier local, un site web, ou un ensemble d'articles Wikipédia — qui se souviennent d'où elles viennent.

Chaque box porte une **carte merirmaid** : `_cachebox.merirmaid`, un diagramme en direct de la structure de la box, régénéré chaque fois que le contenu change. Double-cliquez dessus pour voir la forme d'une box d'un coup d'œil. La carte est un *mirror*, en lecture seule par conception, parce qu'elle reflète la réalité — pour changer la carte, changez la box. Une passe de réconciliation peu coûteuse garde les mirrors honnêtes même quand vous déposez des fichiers depuis Finder dans le dos d'enough.

Ouvrez le **mode cacheawl** depuis la barre supérieure pour une vue à deux volets, projet d'un côté, dépôt de l'autre. Glissez un fichier d'un côté à l'autre pour le copier. Shift-glissez pour le déplacer. Shift-cliquez pour un menu contextuel, et double-cliquez pour ouvrir n'importe quel fichier dans son mode naturel — girraph, merirmaid, lecture/édition, ou le lecteur wiki — directement depuis le dépôt.

### 12.2 Le cachebox et la capture de documents locaux ou web

La **barre d'ingestion** en mode cacheawl (ou une simple demande en conversation) capture du matériel extérieur dans une box :

- **Un chemin local** — réplique un dossier de notes ou de documents dans le dépôt.
- **Un site web** — explore un site de documentation ou de référence jusqu'à une profondeur choisie (plafonnée autour de 500 pages) et le garde en markdown local. Les ingestions web respectent vos interrupteurs de récupération et vos listes blanches, routage Tor compris.
- **Wikipédia** — tire les articles d'un sujet (plafonnés autour de 200) de votre archive wikisink vers du texte permanent, indépendant de tout projet.

Les ingestions tournent en arrière-plan. La box apparaît immédiatement avec un statut « en cours d'ingestion » que vous pouvez observer, et une ingestion échouée le dit plutôt que de prétendre avoir fini. Les outils de cachebox de vos readvisors (lister, créer, ingérer) sont soumis à l'interrupteur broker cacheawl ; votre propre usage du mode cacheawl ne l'est jamais.

Pourquoi s'en donner la peine ? Parce que les dossiers de projet sont un espace de travail et cacheawl un espace de bibliothèque. Ingérez une fois la documentation d'un framework, et chaque futur projet peut s'appuyer dessus hors ligne. Gardez vos notes de référence pérennes dans une box, et chaque readvisor à qui vous parlerez un jour peut les atteindre. Terminez un artefact et déplacez-le dans une box, où il survit à son projet.

---

## 13. Le dictionnaire (FEED)

enough vient avec un dictionnaire bien à lui : **FEED**, le **dictionnaire anglais maison d'enough**. C'est une œuvre originale, écrite pour enough plutôt que sous licence venue d'ailleurs — environ 96 000 mots-vedettes, chacun avec sa prononciation, sa catégorie grammaticale et une définition claire, et la plupart avec des exemples, des formes, une origine, une date de premier emploi, une mesure de sa fréquence, ses rimes, ses parents, et ses équivalents dans cinq autres langues.

Il vit sur votre machine. enough livre le dictionnaire en texte brut et le construit en base de données la première fois qu'il tourne après une installation ou une mise à jour — `~/enough/dict/feed.sqlite` — en arrière-plan, pendant que vous vous occupez d'autre chose. Ouvrez le dictionnaire pendant que ça tourne encore et il affiche *on assemble les caractères…* avec un pourcentage, puis poursuit tout seul. Chercher un mot ne touche jamais le réseau : ce que vous lisez, et les mots dont vous vous êtes demandé le sens, restent sur la machine.

### 13.1 L'ouvrir

Depuis la fenêtre ⚙ UI : le bouton **dictionnaire** se trouve à côté de **aide**, en haut (section 10). Le dictionnaire s'ouvre comme un mode plein cadre, empilé comme les autres (section 14), si bien que ce que vous lisiez est toujours en dessous quand vous le fermez, et Esc vous y ramène.

C'est une surface de lecture. Vous ne pouvez pas taper dans ses entrées ni les réarranger ; ajouter et changer des mots passe par votre readvisor en chef (section 13.7).

### 13.2 Tourner les pages

Il est composé comme un dictionnaire imprimé plutôt que comme une liste qu'on fait défiler : autant d'entrées que la fenêtre peut en contenir, sur deux à quatre colonnes quand il y a de la place, et une page qu'on tourne. → et ←, Page suivante et Page précédente, espace et maj-espace la tournent toutes ; un seul glissement sur le pavé tactile ou un seul cran de molette aussi — une page par geste — et les boutons en bas aussi, qui nomment le mot qui attend sur la page suivante et celui qu'on laisse sur la précédente. Début et Fin vont à la première page et à la dernière.

Le long du haut de chaque page courent les **mots-repères**, comme dans tout dictionnaire imprimé : le premier mot de la page à gauche, le dernier à droite, et entre les deux un rappel de l'ordre dans lequel vous lisez. Un titre marque l'endroit où commence chaque nouveau groupe — une lettre, un domaine, un siècle. En pied de page, un compte de l'endroit où vous êtes — quelles entrées sont sur la page, sur combien au total (il n'y a pas de numéros de page, puisqu'une page contient autant d'entrées que votre fenêtre le permet) — et **ouvrir n'importe où**, qui ouvre le dictionnaire à une page au hasard et éclaire un mot dessus. C'est une bonne façon de perdre dix minutes.

Le long du bord droit se trouve l'**index à onglets**, ces onglets entaillés dans la tranche d'un gros dictionnaire de bureau : un onglet par lettre, chacun aussi haut que sa part du livre, si bien qu'on voit d'un coup d'œil que le S est gras et le X maigre. Cliquez sur un onglet pour ouvrir le dictionnaire à cet endroit. Les onglets suivent l'ordre dans lequel vous lisez — des domaines sous un tri par domaine, des siècles sous un tri par époque — et celui où vous êtes est marqué.

Chaque entrée est brève : le mot-vedette avec des points entre ses syllabes (*lan·tern*), sa prononciation, sa catégorie grammaticale, la définition, une étiquette d'usage quand il y en a une, et quelques mots apparentés, chacun un lien qui tourne à la page de ce mot. ↑ et ↓ déplacent une sélection à travers les entrées ; Entrée, ou un double-clic, ouvre l'entrée sélectionnée en entier (section 13.5). Quand le dictionnaire est étroit — une petite fenêtre, ou serré à côté d'un panneau readvisor ancré — la page devient une seule colonne d'entrées plus fournies, chacune avec une petite jauge de fréquence, une frise du moment où le mot est arrivé, et son domaine.

**Les marques de catégorie grammaticale.** Chaque entrée porte une marque pour chaque catégorie grammaticale qu'elle a, d'une couleur et d'une forme, si bien que la couleur n'est jamais le seul signal : un **carré** pour un nom, un **triangle** pour un verbe, un **losange** pour un adjectif, un **point rond** pour un adverbe, et un **anneau creux** pour tout le reste. Dans les colonnes, la marque se place devant l'abréviation (*n.*, *v.*, *adj.*…) et en fine barre le long du bord de l'entrée ; un mot qui est à la fois nom et verbe porte les deux.

### 13.3 Trier, et trier encore

L'ordre alphabétique n'est que le point de départ. **trier** classe tout le dictionnaire selon l'une de neuf choses — alphabétique, longueur, domaine, époque, catégorie grammaticale, fréquence, syllabes, ajoutés récemment, et provenance — et le bouton à côté inverse l'ordre, en mots simples : *courts d'abord* ou *longs d'abord*, *les plus anciens d'abord* ou *les plus récents d'abord*, *les plus rares d'abord* ou *les plus courants d'abord*.

**puis** est un second ordre à l'intérieur du premier, et c'est là qu'est le plaisir. Triez par domaine, puis par époque, et chaque champ du savoir aligne ses mots dans l'ordre où l'anglais les a ramassés — les plus vieux mots de la musique d'abord, les plus récents à la fin. Triez par longueur, puis par ordre alphabétique, et vous pouvez lire dans l'ordre tous les mots de cinq lettres du livre, ce qui est tout l'après-midi d'un faiseur de mots croisés. Triez par fréquence, les plus rares d'abord, et le dictionnaire s'ouvre sur les mots que presque personne n'emploie. Tant qu'un second ordre est actif, chaque entrée montre en marge sa valeur pour cet ordre.

**plus** ouvre deux courtes rangées. **essayez** contient une poignée d'ordres en un clic — *domaine, puis époque* ; *longueur, puis ordre alphabétique* ; *les plus rares d'abord* ; *époque, puis ordre alphabétique* ; *les mots les plus récents d'abord* ; *les vôtres seulement*. **seulement** restreint le livre à un domaine, une catégorie grammaticale, une bande de fréquence, ou aux mots de FEED ou aux vôtres, et **effacer** lève le tout. Le compte en haut à droite dit combien d'entrées vous regardez, sur combien.

Le dictionnaire se souvient de votre ordre, de vos filtres et de la page où vous étiez, et s'ouvre là la prochaine fois.

### 13.4 Trouver un mot

Tapez dans la boîte de recherche en haut — / ou ⌘F vous y mène — et la page devient les résultats : chaque entrée dont le mot-vedette ou la définition contient ce que vous avez tapé, avec les occurrences marquées. Appuyez sur Entrée sur un mot exact et la recherche s'efface, et le dictionnaire tourne à la page de ce mot à la place, dans l'ordre où vous lisiez. Esc efface la recherche et vous remet sur la page où vous étiez avant elle.

Une forme d'un mot — *ran*, par exemple — vous mène au mot dont elle dépend, et la carte d'une forme que vous avez cherchée dit de quelle forme de quoi il s'agit. Un mot que FEED n'a pas ouvre sa carte (section 13.5) avec la nouvelle, quelques mots voisins qu'il a bel et bien, et l'endroit où le mot tomberait s'il y était.

### 13.5 La carte d'un mot

Double-cliquez sur une entrée, ou sélectionnez-la et appuyez sur Entrée, et elle s'ouvre en grand, comme une carte par-dessus ce que vous faisiez. Tout ce que FEED sait du mot y figure, et la plupart dès la première vue :

- le mot-vedette, ses syllabes et sa prononciation, et ses catégories grammaticales avec leurs marques ;
- sa fréquence, en jauge de 0 à 8 avec le nom de la bande à côté ;
- une bande de faits — domaine (et combien de mots le partagent), premier emploi, syllabes, lettres, et si l'entrée est celle de FEED ou la vôtre ;
- une frise de l'ancien anglais aux années 2020, avec l'arrivée du mot marquée dessus ;
- le **sens**, toute **note d'usage**, des **exemples** où le mot est mis en évidence, ses **formes** (pluriels, temps et le reste, chacun avec sa propre prononciation), ce dont il est une **forme de** s'il en est une, et son **origine**.

Trois onglets contiennent le reste, à un clic (ou 1, 2 et 3) : **mots** — synonymes, antonymes, mots apparentés et homophones ; **rimes** — parfaites et approchées ; et **langues** — le mot posé à côté de ses équivalents en français, espagnol, allemand, chinois et japonais, avec la définition traduite dans chacune. Quand FEED n'a rien enregistré pour un mot, la carte le dit, plutôt que de laisser un blanc là où vous iriez chercher.

**Aller de mot en mot.** Chaque mot listé sur la carte est un lien, et chaque mot de la définition, des exemples et de l'origine aussi : cliquez sur l'un d'eux et la carte devient celle de ce mot. Le chemin parcouru s'affiche en haut sous le nom **votre parcours**, et **‹ retour** (ou ⌫) le refait à rebours, un pas à la fois. ← et → passent à l'entrée précédente et à la suivante dans l'ordre où vous lisez, avec *entrée n sur m* pour dire où vous en êtes. **montrer sur sa page** — **ouvrir dans le dictionnaire**, quand vous veniez d'ailleurs — ferme la carte et ouvre le dictionnaire sur le mot. Esc, la ×, ou un clic en dehors de la carte la ferme.

### 13.6 « entrée du dictionnaire », partout où vous lisez

Faites un clic droit sur un mot — dans la face lecture ou la face édition d'un document, dans la conversation, sur une page de composure, dans un article wikisink, dans ce manuel — et un petit menu propose **entrée du dictionnaire**, qui ouvre la carte de ce mot par-dessus ce que vous faites, et **copier**. Sélectionnez d'abord une courte expression et faites un clic droit à l'intérieur, et c'est l'expression qui est cherchée. Dans le dictionnaire, la même entrée de menu tourne à la page du mot ; dans la carte, elle y emmène la carte. ⇧⌘D fait de même pour le mot sélectionné, ou le mot sous le curseur, sans aucun menu. Sur une composure, le menu que vous obtenez déjà en faisant un clic droit sur un module gagne la même entrée dès que le pointeur est sur un mot.

Le menu du système n'a pas disparu ; il s'est décalé d'une touche. Un clic droit qui n'est pas sur un mot — entre deux mots, au-delà de la fin d'une ligne, sur un lien, sur une image — donne le menu du système exactement comme toujours. Et un clic droit avec **maj** enfoncée donne à chaque fois le menu du système, mot ou pas : c'est le chemin vers les suggestions d'orthographe, la recherche propre au système, et coller dans un champ de texte. Le menu le dit sur sa dernière ligne, il n'y a donc rien à retenir.

### 13.7 Votre propre dictionnaire

FEED lui-même ne change jamais sous vos pieds, mais ce n'est pas le seul dictionnaire ici. À côté se trouve **le vôtre**, qui commence vide et ne contient que ce que vous y mettez : un mot que votre famille a inventé, un terme de votre métier, un nom que vous donnez à une chose, une création de votre cru — ou votre propre version d'un mot que FEED a déjà.

Vous y ajoutez en le demandant à votre readvisor en chef. « Mets *glimmerwick* dans mon dictionnaire. » « Mon équipe appelle *dronefest* une réunion qui aurait dû être un e-mail — tu l'ajoutes ? » « Je voudrais ma propre définition de *draft*. » La conversation se déroule comme le ferait celle d'un lexicographe soigneux. Votre readvisor cherche d'abord le mot, et si FEED l'a, il le dit et propose de vous le montrer plutôt que d'en ajouter discrètement un second. S'il est nouveau, il rédige ce qui peut l'être — prononciation, catégorie grammaticale, syllabes, formes — et vous demande ce que vous seul savez : ce qu'il veut dire, comment et où vous l'employez, qui le dit, d'où il vient, une question ou deux à la fois. Puis il vous relit l'entrée en mots simples et attend un oui avant d'écrire quoi que ce soit. Ensuite il vous signalera, une fois, quelles parties sont encore vides ; les laisser vides est très bien.

Vos mots sont entremêlés à ceux de FEED sur chaque page et dans chaque ordre, marqués **vôtre**, et *les vôtres seulement* sous **plus** les montre à part. Un mot présent dans les deux dictionnaires est le vôtre : votre version remplace celle de FEED partout dans enough — sur la page, sur la carte (marquée *remplace FEED*), et dans ce que votre readvisor trouve quand il cherche le mot.

Ils vivent dans un seul fichier, `~/enough/dict/user-dictionary.sqlite`, à part de celui de FEED et valable pour toute la machine comme votre thème, de sorte que chaque projet voit les mêmes mots. Une mise à jour reconstruit le fichier de FEED de zéro et ne touche jamais au vôtre.

Pour retirer une de vos entrées, ouvrez sa carte et appuyez sur **supprimer votre entrée** ; il demande d'abord. Supprimer votre version d'un mot de FEED ramène l'entrée propre de FEED. Modifier une entrée est une autre conversation — « change l'exemple de *glimmerwick* » — puisque le dictionnaire lui-même est fait pour la lecture seule.

Votre readvisor a le dictionnaire sous la main dans chaque projet, avec ou sans compétence. La compétence `lexicographer` (section 19.4) est pour quand vous ajouterez souvent des mots : activée, elle emporte à chaque tour tout le style maison de FEED, de sorte que vos entrées sonnent comme le reste du livre sans que votre readvisor ait à aller chercher d'abord le guide de style.

---

---

## 14. Empilement de plusieurs modes actifs

Les modes plein cadre d'enough — lecture/édition, girraph, merirmaid, wikisink, cacheawl, le dictionnaire, ce manuel — ne se remplacent pas les uns les autres. Ils **s'empilent**, comme des feuilles de papier. Ouvrez cacheawl, ouvrez un girraph depuis l'intérieur d'une box, ouvrez un fichier de notes par-dessus : trois modes de profondeur, et fermer chacun révèle celui en dessous exactement comme vous l'aviez laissé. Même position de défilement, même descente, mêmes modifications non enregistrées.

La barre supérieure montre un indicateur carré par mode ouvert, le plus récent à gauche. Chacun porte un petit ruban croix-rouge qui ferme ce mode précis, même un enseveli. Cliquez sur l'indicateur d'un mode enseveli pour le remonter au sommet sans déranger le reste. Quand le dernier se ferme, vous voilà de retour sur la composure — la pile vide (section 4).

**Le carré de base.** À l'extrémité droite de ces indicateurs s'en trouve un qui est toujours là et n'a pas de ruban : la composure. Il n'y a rien à fermer, parce que c'est le plancher. Cliquer dessus, c'est le geste du **coup d'œil** de la section 4.8 — chaque mode empilé se masque, vous regardez le canevas, et un nouveau clic dessus (ou sur n'importe quel autre indicateur) les ramène tous intacts.

**Le panneau readvisor n'est pas du tout dans la pile.** C'est une colonne à côté (section 5) : un panneau ancré et trois modes empilés coexistent donc sans se gêner mutuellement, et Échap ne ferme jamais le panneau quand il est ancré.

**Échap, dans l'ordre.** Échap veut dire *sortir de la chose la plus intérieure*, et la chose la plus intérieure n'est pas toujours un mode :

1. une fenêtre modale ouverte, qui gère son propre Échap ;
2. une surcouche de confirmation ;
3. un champ de texte où vous êtes en train de taper — où Échap est délibérément inerte, pour qu'une pression involontaire ne puisse pas jeter un message que vous étiez en train de composer (un champ de recherche fait exception : là, Échap efface d'abord la recherche, puis lâche prise) ;
4. un menu de composure ouvert ;
5. un panneau readvisor en plein écran, qui retombe en panneau ancré ;
6. un coup d'œil, qui remet les modes empilés en place ;
7. et seulement alors, le mode le plus au-dessus.

Deux commodités à connaître :

- Le mini panneau lecture/édition flotte *par-dessus* un mode plein cadre, donc vous pouvez garder un document sous le coude en travaillant, disons, en mode girraph en dessous.
- Ouvrir un mode déjà quelque part dans la pile ne le duplique pas. Ça retargète et remonte celui que vous aviez déjà.

---

## 15. La fenêtre de modèle

Le badge de modèle dans la barre supérieure ouvre la fenêtre de modèle : quel cerveau vous répond, ce qui est disponible d'autre, et — si vous le choisissez — l'emplacement cloud.

### 15.1 Modèles locaux : vue d'ensemble et recommandations d'usage

Sept modèles locaux pris en charge — et la fenêtre est maintenant aussi l'endroit où vous les installez. Chaque ligne que vous n'avez pas encore montre sa taille de téléchargement et un verdict de faisabilité calculé par rapport à la mémoire et à l'espace disque libre de *cette machine* : ✓ confortable, ~ juste, ✗ non recommandé. Les téléchargements tournent avec une barre de progression en direct, survivent à une fermeture (ils reprennent là où ils se sont arrêtés), et peuvent être annulés sans perdre la partie que vous avez déjà. Les modèles installés changent en un clic, et n'importe quel modèle sauf l'actif peut être supprimé depuis sa ligne quand vous voulez récupérer l'espace disque.

| petit nom | modèle | disque | RAM min | notes |
|---|---|---|---|---|
| **G40-04** | Gemma 4 4B (E4B) | ~5,4 Go | 8 Go | le plus petit ; tient partout ; le défaut |
| **Q35-09** | Qwen3.5-9B | ~5,9 Go | 10 Go | taille moyenne équilibrée ; décodage spéculatif MTP |
| **G40-12** | Gemma 4 12B (QAT) | ~7,0 Go | 12 Go | entraîné avec quantification consciente ; le point idéal des 16 Go |
| **G40-26** | Gemma 4 26B MoE (4B actifs) | ~15,6 Go | 20 Go | qualité de grand modèle à la vitesse d'un modèle moyen |
| **Q36-27** | Qwen3.6-27B dense | ~17,1 Go | 22 Go | le poids lourd chevronné ; MTP ; longue haleine |
| **Q38-04** | Qwen3.8 27B (4 bits) | ~19 Go + 1,7 brouillon | 24 Go | le plus récent Qwen ; ébauche sa propre spéculation |
| **Q38-16** | Qwen3.8 27B (16 bits) | ~54 Go + 3,2 brouillon | 64 Go | pleine précision, pour les plus gros Mac |

Un pli de nommage, pour qu'il ne vous piège jamais : dans les deux noms Q38, le chiffre après le tiret est la **largeur de quantification**, pas le nombre de paramètres — Q38-04 et Q38-16 sont le *même* modèle à 27 milliards de paramètres, en précision 4 bits et 16 bits. (G40-04, issu de l'ancienne convention, est réellement un modèle à 4 milliards de paramètres.) Les étiquettes dans la fenêtre l'expliquent en toutes lettres pour que les petits noms n'aient jamais à le faire.

Règles de base. Sur une machine de 8 à 16 Go, vivez sur G40-04, et faites de G40-12 la mise à niveau une fois que vous avez de la marge — l'entraînement avec quantification consciente lui donne une sortie inhabituellement propre pour sa taille. Sur 32 Go, G40-12 ou Q35-09 est un cheval de bataille quotidien confortable, avec G40-26 ou Q38-04 pour le travail de synthèse plus difficile. Sur 64 Go et plus, Q38-04 ou Q36-27 comme défaut, et arrêtez d'y penser. Q38-16 est sa propre catégorie : le poids lourd pleine précision pour les machines à mémoire unifiée sérieuse et ~57 Go de disque à revendre — si vous avez un Mac Studio et voulez le plafond, voici le plafond. Les fenêtres de contexte s'adaptent automatiquement à votre RAM — chaque modèle est fourni avec un défaut sensé par palier de RAM, modifiable dans la config — et les builds Qwen portent la prédiction multi-tokens pour de la vitesse en bonus gratuite : intégrée dans le fichier de modèle pour Q35/Q36, et via un petit fichier « brouillon » compagnon pour la paire Q38, qui se télécharge automatiquement avec.

Encore une note pour les installations terminal : un modèle peut être *téléchargé* sur n'importe quel llama.cpp mais ne *tourner* que sur un build assez récent. Si le vôtre est trop vieux pour un nouveau modèle, la fenêtre le dit et nomme le correctif (`brew upgrade llama.cpp`). Les installations application ne voient jamais cette note — l'application embarque son propre moteur d'inférence.

Changer de modèle redémarre le serveur d'inférence local et vide la conversation en mémoire. Vos fichiers, journaux, et état de requêtes persistent tous ; un changement vous coûte l'historique de discussion, pas le travail.

### 15.2 Support OpenRouter (l'emplacement OPRO-API)

enough est local-d'abord, pas local-seulement. Un cinquième emplacement de modèle, **OPRO-API**, route à travers OpenRouter vers des modèles cloud. Il est désactivé par défaut, délibérément laborieux à activer, et honnête sur le compromis : vos prompts et sorties quittent la machine, en échange d'une capacité de modèle de pointe et, parfois, d'un coût plus bas que ce que le matériel et l'électricité d'un modèle local comparable exigeraient.

Pour l'activer : désactivez **local models only** dans le broker, puis cliquez sur OPRO-API dans la fenêtre de modèle. Un assistant en trois écrans vous guide — trois cases de confirmation explicites (vous avez un compte, vous comprenez la facturation, vous comprenez le compromis de confidentialité), puis votre clé API, puis une vérification de santé en direct. La clé est stockée dans le Trousseau macOS. Elle n'est jamais écrite dans aucun fichier, vos readvisors n'ont aucun moyen de la lire, et le broker refuse les commandes shell qui ressemblent même de loin à des tentatives d'y accéder. Une fois vérifiée, OPRO-API devient sélectionnable comme n'importe quel autre modèle, et son panneau de réglages propose retester, mettre à jour la clé, supprimer la clé, et votre choix de n'importe quel id de modèle OpenRouter.

Deux choses gardent l'usage du cloud responsable :

- **Tout est mis en cache localement.** Chaque échange cloud est écrit dans `rness/io/cloud-cache/` avec les comptes de tokens et un index — une trace papier locale que vos readvisors locaux peuvent lire plus tard.
- **`cloud_pipeline`** laisse vos readvisors traiter par lots de gros travaux à travers l'emplacement cloud — jusqu'à 200 étapes, avec mise en cache par étape, résumé optionnel par étape, et une passe de compilation finale — en écrivant les résultats sur le disque plutôt qu'en inondant la conversation. Demandez « un cloud pipeline qui rédige les douze résumés de chapitre » et le gros du travail se passe hors bande, entièrement journalisé.


### 15.3 `/pal` — une seule question vers l'extérieur

Parfois votre modèle local est dépassé et vous aimeriez un avis extérieur. Un **pal**, c'est ça : pas un nouveau réglage ni un second compte, juste le modèle cloud que vous avez déjà configuré dans l'emplacement OPRO-API, joint une fois, à la main, depuis un tour par ailleurs local.

Commencez un message par `/pal` et le reste est la demande :

`/pal quel est aujourd'hui l'état de l'art de la reconnaissance vocale sur l'appareil ?`

Trois choses se produisent alors, dans l'ordre. Votre readvisor en chef y réfléchit ici d'abord, avec ce qui est déjà sur la machine — ses propres connaissances, les fichiers de votre projet, les outils wiki — et détermine ce qu'il ne peut vraiment pas trancher en local. Il compose **une seule** invite et l'envoie au modèle cloud. Puis il vous répond de sa propre voix, en disant clairement quelles parties viennent du pal et lesquelles sont les siennes.

**Vous voyez ce qui est parti.** Avant que la réponse n'arrive, le texte exact qui est sorti apparaît dans sa propre bulle, mot pour mot — jamais raccourci, jamais résumé en chemin vers l'écran — avec la réponse en dessous. Les deux sont toujours là après un rechargement, et les deux sont écrits dans votre journal de session et dans le cache cloud. Taper `/pal` *est* le consentement ; il n'y a pas de seconde étape de confirmation, parce qu'une confirmation qui apparaît à chaque fois est un bouton qu'on apprend à cliquer sans lire. Ce qui la remplace, c'est que vous pouvez toujours voir ce qui est parti.

**Le verrou est celui de l'emplacement cloud, exactement le même.** `/pal` marche quand **local models only** est désactivé dans le broker, qu'une clé est stockée, et que la dernière vérification de santé est passée (15.2). Si l'un de ces points n'est pas vrai, `/pal` vous dit lequel et comment le réparer — et aucun tour ne tourne, donc rien n'est dépensé et rien ne sort. Tapez `/` comme premier caractère dans la zone de saisie et une ligne d'indice vous dit la même chose avant que vous ne vous engagiez : grisée avec la raison quand l'emplacement n'est pas utilisable, et nommant le modèle qu'elle interrogerait quand il l'est, ce qui est toute la différence entre une commande et une surprise sur votre facture.

**Un appel par `/pal`.** Votre readvisor obtient exactement une question vers l'extérieur par message que vous commencez ainsi. Si la réponse n'a pas fait le tour, il le dit et vous pouvez en envoyer une autre. Et rien ne quitte cette machine lors d'un autre tour : sans `/pal` devant, l'outil n'est tout simplement pas là, et un readvisor qui pense qu'un avis extérieur aiderait doit le dire et vous laisser décider.

Si le modèle à qui vous parlez déjà *est* OPRO-API, il n'y a pas de pal à interroger — le modèle cloud est celui à qui vous parlez. `/pal` le dit, laisse tomber le jeton, et envoie le reste du message comme d'habitude.

**Un pal est figé à sa date de coupure d'entraînement, sauf si vous demandez le web.** OpenRouter documente un suffixe fait exactement pour ça : mettez `:online` à la fin de l'id du modèle dans le panneau de réglages OPRO-API — `anthropic/claude-sonnet-4.5:online` — et votre question sort avec des résultats de recherche web attachés. C'est une fonctionnalité propre à OpenRouter et il n'y a aucun code de notre part derrière ; enough transmet l'id du modèle tel quel, et les bulles l'affichent avec le suffixe, parce que ça coûte un supplément par recherche et que vous devez pouvoir voir que vous l'avez demandé.

---

## 16. Paradigmes

Un paradigme est le cadre de raisonnement dans lequel travaillent vos readvisors — les règles d'engagement pour la façon dont le travail se déroule. Un seul est actif à la fois (affiché en haut de la barre latérale ; cliquez sur ● pour changer), et le texte complet du paradigme actif voyage dans le prompt système à chaque tour. Votre readvisor en chef voit aussi un catalogue d'une ligne des autres, pour pouvoir suggérer un changement — ou en faire un — quand votre demande serait mieux servie ailleurs. Un changement fait pour vous n'a rien d'exotique : le nom du paradigme est écrit dans `rness/active-paradigm` et on vous dit que c'est arrivé.

### 16.1 text-planning

**L'accueil.** Chaque nouveau projet démarre ici, et chaque autre paradigme y revient quand son travail est fait. La plupart du temps, ça ne ressemble pas du tout à un cadre : une conversation libre, une seule voix, pour les questions, la lecture, la recherche, la révision, le travail sur les fichiers, et la rédaction quand vous demandez de rédiger. Il porte les conventions permanentes — savoir que « les parties jaunes » veut dire vos surlignages, où vont les fichiers générés, comment les pages web sont récupérées — et c'est l'aiguilleur qui remarque quand un autre paradigme servirait mieux une demande, et bascule.

C'est aussi là qu'un texte se planifie, et c'est la longue piste d'élan avant la prose : faire passer un roman, un recueil d'essais, un livre non-fictionnel, un article ou un manifeste de « je crois que je veux écrire quelque chose » à un plan utilisable. Rien de cette mécanique n'apparaît tant que vous n'avez pas montré une intention de planifier — « aide-moi à planifier un roman », « structurons mon recueil d'essais » — et aucune compétence n'a besoin d'être activée pour cela. Votre readvisor en chef construit alors un document de plan avec vous à la racine du projet — patiemment, itérativement, sur autant de sessions qu'il faut — et, sur demande, génère par section des *échafaudages* : des guides structurels (beats, en-têtes, rappels de voix, budgets de mots) que vous développez vous-même en prose. La règle qui le définit : **le plan et les échafaudages ne contiennent jamais de prose.** Ils ne tiennent que de la structure, et votre voix reste votre voix. La rédaction est une chose à part que vous pouvez demander en toutes lettres — « rédige le chapitre 1 d'après le plan » — et elle est écrite dans son propre fichier, jamais dans le plan ; votre readvisor ne la proposera pas de lui-même. Un projet qui se révèle être un mémoire est orienté vers `memoir-dialectic` (section 19.5), construite spécifiquement pour cela.

**Si un projet était sur `default`.** `default` était le paradigme d'accueil jusqu'à cette passe, et text-planning a absorbé tout ce qu'il faisait. Un projet qui avait `default` actif passe à text-planning la prochaine fois que vous l'ouvrez, votre réglage des bulles d'aide restant tel qu'il était. La seule exception est un projet où vous avez personnalisé `default.md` en un fichier à vous : cette copie est la vôtre, le projet la garde donc, et continue de s'en servir, jusqu'à ce que vous changiez.

### 16.2 translation

Déclare la traduction hors ligne comme une capacité de premier ordre. Il se marie avec la compétence `translator` (section 19.8) : quand une demande implique de faire passer du texte d'une langue humaine à une autre, votre readvisor bascule ici, et si la compétence est désactivée, il vous dit ce que vous manquez — et continue de le dire jusqu'à ce que vous l'activiez. Compétence activée, vous avez un traducteur local d'environ 419 langues, sans compte, sans limite de débit, et sans dépendance réseau.

### 16.3 workflow-design

Le paradigme à propos d'enough lui-même, actif chaque fois que vous créez ou changez le flux de travail plutôt que de travailler à l'intérieur : nouvelles compétences, nouveaux readvisors, nouveaux paradigmes, modifications d'AGENT.md ou de MOTIVATION.md. Ici votre readvisor en chef se comporte comme un collaborateur de conception réfléchi — des questions de clarification avant de construire (périmètre ? nom ? conditions de déclenchement ?), des alternatives quand votre premier instinct pourrait être plus affûté, et un fichier de requête suivi pour chaque construction, puisque les changements de flux de travail survivent aux conversations qui les produisent. C'est le paradigme qui rend la section 3 réelle.

---

## 17. Readvisors

Un **readvisor** est un jugement que vous pouvez garder : son propre `AGENT.md` et son propre `MOTIVATION.md`, les deux mêmes fichiers qui définissent votre readvisor en chef, circonscrits à une manière particulière de lire un problème. Activez-les par projet dans la section **readvisors** de la barre latérale.

Celui en haut du panneau readvisor est votre **readvisor en chef**, et d'origine il s'appelle **Ed**. Ce nom est à vous et vous pouvez le changer — **renommer votre readvisor en chef**, dans l'en-tête de la fenêtre broker (section 9). Le chef n'est pas d'une autre nature que les autres ; c'est simplement celui qui répond quand vous n'avez demandé personne en particulier.

**Plusieurs readvisors, une seule voix.** Activez-en trois et vous n'obtenez pas trois réponses. En conversation ordinaire, leurs perspectives, leur expertise et leurs mises en garde sont fondues dans ce que dit votre chef — une seule voix, parfois faite de plusieurs. Quand une perspective particulière porte un argument, on vous dira en général laquelle. Si vous les voulez parlant séparément, sous leurs propres noms, chacun leur tour, c'est exactement ce qu'est un **conseil** (section 18).

**Trois provenances**, et la ligne de la barre latérale dit laquelle :

- **fourni** — les deux ci-dessous, qui arrivent comme des liens vers les défauts d'enough, comme tout autre composant fourni.
- **global** — tout ce qui se trouve dans `~/enough/readvisors/`, qui est à vous et que tous les projets de cette machine voient. Ce dossier n'est jamais créé pour vous : il apparaît la première fois que quelque chose y dépose un readvisor. (C'est celui où l'on peut écrire. Le dossier des défauts à l'intérieur d'une installation de bureau est scellé.)
- **projet** — un vrai dossier dans le `rness/readvisors/` de ce projet, appartenant à ce projet seul.

Un readvisor global et un readvisor fourni portant le même nom perdent face à un readvisor local au projet ; la copie propre à un projet l'emporte toujours, et c'est ce qui donne du sens à « personnaliser ».

**En retirer un.** Les lignes non fournies portent un ×. Il demande d'abord, parce qu'il supprime des fichiers : le dossier d'un readvisor de projet s'en va, un readvisor global s'en va de `~/enough/readvisors/` et de la liste de ce projet. Ce qu'enough a fourni ne peut pas être retiré de cette façon — il n'y a rien là à supprimer qu'une mise à jour ne remettrait pas. Et un nom retiré est aussi effacé de la liste des désactivés du projet, pour qu'un readvisor du même nom arrivant plus tard ne se retrouve pas mystérieusement éteint.

### 17.1 block-breaker

Un spécialiste du blocage d'écriture, distillé à partir des réponses d'un vrai écrivain sur la façon dont il dissout le fait d'être coincé — ce qui est exactement ce que fait la compétence `readvisory` (section 19.6), et voici à quoi ressemble ce qu'elle produit. Il diagnostique avant de prescrire — à court d'idées, à court de cran, à court de structure, et à court de permission sont quatre problèmes différents — puis fait appel à des contraintes, du brainstorming par répétitions (« dix variations, puis on taille »), des recadrages étranges, et, quand on le veut, de vraies phrases suivantes. Implacablement anti-défaitiste. Sa croyance centrale : pour quiconque écrit volontairement, le blocage se résout toujours, parce que les règles ont été inventées et que le remède peut l'être aussi.

### 17.2 open-skeptic

Un « oiseau de mauvais augure éclairable » : sincèrement enthousiaste pour l'IA là où elle est forte, professionnellement méfiant là où elle est survendue. Convoquez-le quand vous êtes sur le point de construire un flux de travail et voulez que les modes d'échec soient nommés tôt. Il résiste à l'idée de demander à l'IA de répliquer l'expérience humaine, aux chaînes d'erreurs qui s'accumulent sans relecture humaine, et à la confiance fluide qui fait le travail de l'expertise — tout en applaudissant l'IA comme moteur de collation, prothèse de connaissance, et partenaire de répétition. Il change d'avis face aux preuves : montrez-lui un flux de travail qui marche et il le dit, tout simplement.

### 17.3 Construire le vôtre

Deux exemples, une seule forme. Chaque readvisor est la même paire de fichiers markdown avec les mêmes intertitres : `AGENT.md`, qui s'ouvre sur le nom d'affichage que vous voyez dans la barre latérale puis décrit comment cette personne pense, et `MOTIVATION.md`, qui dit ce à quoi elle tient, ce contre quoi elle protège, et où elle se trompe. Cette forme est vérifiée à l'installation — pas au chargement, si bien qu'un readvisor que vous avez écrit à la main il y a des années fonctionne encore exactement comme avant.

Vous pouvez écrire les deux fichiers vous-même. La voie prise en charge est la **compétence `readvisory`** (section 19.6), qui en construit un à partir du jugement d'une vraie personne en lui posant des questions — vous, en direct, ou quelqu'un dont vous aimeriez avoir l'avis sous la main, via un questionnaire que vous lui envoyez. Les readvisors sont le moyen le moins coûteux d'ajouter une lecture qui vous manque : un canard en plastique socratique, un relecteur de conformité, votre lecteur cible, le rédacteur qui attrapait toujours la chose que vous ne pouviez pas voir.

---


## 18. Conseils

Un **conseil** est une composure où vos readvisors réfléchissent à une seule chose chacun leur tour, par écrit, sous leurs propres noms, pendant que vous regardez ça se produire. C'est l'autre moitié de la section 17 : les mêmes readvisors qui sont d'ordinaire fondus en une seule voix, dépliés, en désaccord et pour de bon.

C'est une composure ordinaire, donc tout ce que dit la section 4 s'applique encore. Le **brief** est en haut ; chaque intervention atterrit en dessous sous forme de carte titrée de qui a parlé et de quel tour c'était, teintée à la couleur de cette personne — votre chef sur papier, vous en bleu, chaque readvisor dans sa propre couleur pour toute la durée du conseil, la conclusion en encre. La colonne se remet d'aplomb à mesure qu'elle grandit, même si vous avez beaucoup déplacé les choses.

Les interventions appartiennent au conseil, pas à vous. Vous pouvez les déplacer, les restyler, les commenter, et dézoomer pour lire l'ensemble comme une colonne de faces — mais vous ne pouvez pas en réécrire une, et aucun readvisor ne le peut non plus. Une transcription que vous pouvez modifier est une suggestion, pas un compte rendu. Le brief, lui, reste un module ordinaire et reste modifiable.

### 18.1 En mettre un en place

Nouvelle composure à partir du form **council** et vous obtenez une carte de préparation avec quatre champs pour le brief :

- **entrée** — la chose à trancher. Une seule question, aussi nette que vous pouvez la faire.
- **paramètres** — comment vous voulez que ça se passe. « Deux tours, puis on décide. »
- **contraintes** — ce qui est hors de propos. « Ne réécrivez pas la prose. »
- **sortie souhaitée** — l'une des trois : **une réponse tranchée**, écrite sur le canevas à la fin ; **un document**, écrit à un chemin que vous nommez ; ou **une nouvelle composure**, tout un tableau de cartes construit à partir de ce que le conseil a décidé. Choisissez composure et une seconde commande apparaît à côté pour la disposition — *scaffold*, où chaque groupe de cartes est une colonne, ou *cards*, où chaque groupe est une ligne. Ce que chacune fait réellement à la fin, c'est la 18.3.

Ensuite, la salle. La liste à cocher commence par votre readvisor en chef, chaque readvisor que vous avez activé dans ce projet, et **vous** ; décochez qui vous ne voulez pas. Douze au maximum, et deux participants ne peuvent pas porter le même nom, parce qu'une intervention est attribuée par nom et que deux Nadia, ce n'est pas un conseil, c'est un quiproquo. **tours max** est à 3 par défaut et peut aller de 1 à 20.

Chaque ligne de participant accepte aussi une **charge** facultative : une ligne qui dit ce que cette personne est là pour faire. « garde la continuité. » « défend le lecteur. » « deuxième paire d'yeux. » Elle entre dans les instructions propres à ce participant et à personne d'autre, en dernier, après tout ce qu'on lui a déjà dit — c'est la chose la plus précise dont il dispose, et la plus facile à enterrer pour un long profil. Une ligne, c'est toute l'idée ; 200 caractères est le plafond, et tout ce qui dépasse revient refusé plutôt que discrètement rogné, parce qu'une demi-charge est un autre métier. Les charges partent aussi dans l'export de la transcription, à côté du nom, pour qu'un lecteur, des mois plus tard, sache qui défendait quoi et pourquoi.

**convoquer** lance la séance.

### 18.2 Le faire tourner

Six commandes, et elles font exactement ce qu'elles disent.

- **tour suivant** — une intervention, de celui dont c'est le tour.
- **faire un tour** — des tours jusqu'à ce que la rotation revienne à son point de départ. Appuyée juste après avoir convoqué, ça veut dire tout le monde ; appuyée quand il reste un créneau, ça veut dire un.
- **aller jusqu'au bout** — des tours de table jusqu'à votre maximum, en arrière-plan, avec un compte rendu au fil de l'eau.
- **mettre en pause** — s'arrête après l'intervention en cours de rédaction. Une intervention à moitié écrite et jetée est une plus mauvaise surprise qu'un paragraphe de trop.
- **le brief** — retour à la carte de préparation, pour relire ce sur quoi tout le monde travaille ou pour changer la sortie avant de conclure.
- **conclure** — le dernier tour. C'est la 18.3.

Les tours arrivent en flux continu. Une carte apparaît au pied de la colonne avec le nom de l'orateur et le numéro de tour dessus, se remplit à mesure que les mots arrivent, et se fixe en vrai module quand l'intervention est finie. La rotation, c'est le chef puis les readvisors dans l'ordre où ils sont listés ; ça tourne, et un tour de table se referme quand la boucle est bouclée.

**Vous pouvez dire quelque chose à tout moment.** La zone de saisie au pied du conseil prend votre propre intervention et elle entre comme une carte au même titre que celle de n'importe qui d'autre, teintée en bleu. Si personne ne parle, elle atterrit tout de suite ; si un tour est en cours, elle prend le créneau juste après et s'affiche en attente jusque-là. Dans les deux cas c'est une *interjection*, pas un remaniement : le readvisor dont c'était le tour parle quand même ensuite.

**Vous pouvez aussi poser une question à un pal.** Si l'emplacement cloud est utilisable (15.3), tapez `/pal` et votre demande dans la zone de saisie du conseil — `/pal est-ce que le motif autour duquel on tourne a un nom ?` — et votre chef distille la discussion jusqu'ici et votre question en une seule invite autonome, l'envoie dehors, et la réponse atterrit comme une intervention dans sa propre teinte grise, dite par `pal · <id du modèle>`. L'invite qui a quitté la machine est repliée en haut de cette carte : refermée pour que vingt interventions restent lisibles, jamais cachée, à un clic de s'ouvrir. Comme vos propres interventions, c'est une interjection — elle prend un numéro de tour mais pas un créneau, donc celui qui allait parler parle quand même ensuite, et le tour de table n'avance pas.

**Le panneau readvisor est fermé pour la durée**, son interrupteur désactivé et une infobulle expliquant pourquoi (section 5.1). Les conseils et la discussion partagent un seul modèle et il n'y en a qu'un : un tour de discussion ferait donc la queue derrière le conseil ou se battrait avec lui. C'est vrai dans l'autre sens aussi : une commande de conseil pressée pendant que votre chef est en train de répondre dans la discussion revient avec une phrase qui le dit, plutôt que d'attendre en silence.

### 18.3 Conclure : la réponse, le document, la composure, la transcription

**conclure** lance un dernier tour où votre readvisor en chef dit où ça atterrit — en créditant les arguments qui l'ont emporté, en nommant le désaccord qui ne s'est pas résolu plutôt qu'en l'aplanissant, et en disant ce qui reste ouvert. Cette intervention est versée au dossier comme n'importe quelle autre, teintée en encre.

Ce qui se passe ensuite dépend de la **sortie souhaitée** que vous avez choisie à la préparation :

- **une réponse tranchée** — rien de plus. Cette dernière carte est la sortie, et elle est sur le canevas, là où est le conseil.
- **un document dans ce projet** — la conclusion est écrite comme fichier markdown à un chemin de votre projet que vous nommez. Ça passe par la même porte que toute autre écriture de fichier, avec les mêmes listes blanches et la même annulation, et ça n'écrasera pas un fichier existant tant que vous n'avez pas vu la confirmation et dit oui. Ensuite, un module de lien est ajouté sous la conclusion et pointe vers lui, pour que le document soit à un clic du conseil qui l'a produit.
- **une composure** — la conclusion revient sous forme de plan, et enough le construit en une nouvelle composure à côté de celle-ci, dans `rness/io/composure/<conseil>-output-<date>.comp`, dans la disposition que vous avez choisie à la préparation. Chaque groupe est une colonne ou une ligne, chaque carte est un morceau de ce que le conseil a décidé, et ce qu'il n'a *pas* tranché peut ressortir en question ouverte — une carte titrée `[gap: qui s'occupe de la migration ?]`, teintée pour que vous puissiez toutes les retrouver d'un coup d'œil. Un module de lien est ajouté sous la conclusion et pointe vers le nouveau fichier, pour que le tableau soit à un clic du conseil qui l'a produit. Ça n'écrase jamais un fichier existant : un deuxième reçoit `-2`.

Cette dernière option demande à un modèle d'écrire des titres dans une forme exacte, et tous les modèles n'y arrivent pas du premier coup. Si le plan ne peut pas être lu, enough redemande une fois de plus avec la grammaire écrite noir sur blanc. Si la deuxième tentative ne se lit pas non plus, vous obtenez la conclusion sous forme de carte-réponse ordinaire à la place, avec une ligne qui dit ce qui s'est passé, et aucun fichier n'est écrit. La décision du conseil n'est jamais jetée parce que les titres sont sortis de travers — et ce n'est jamais retenté une troisième fois, parce qu'un conseil qui a déjà décidé ne devrait pas dépenser deux tours de plus en mise en forme.

Dans tous les cas, l'ensemble est aussi exporté en markdown brut vers `rness/knowledge/councils/<date>-<titre>.md` : le brief, qui était dans la salle et ce que chacun y faisait, le nombre de tours, et chaque intervention dans l'ordre. Ça n'écrase jamais un export antérieur. Un conseil qui a eu lieu est une chose que vous pouvez grep-er, citer, et donner à quelqu'un, des mois après que la composure a été traînée ailleurs.

Un conseil conclu est terminé. Les commandes s'en vont, et ce qu'il vous montre à partir de là, c'est le chemin de la transcription, la sortie, et de quoi le reconvoquer (18.5).

### 18.4 Ce que ça coûte, honnêtement

**C'est lent, et c'est fait pour.** Chaque intervention est un tour de modèle complet — le participant lit le brief et tout ce qui a été dit jusque-là, et écrit. Quatre participants sur trois tours de table, ça fait douze tours, l'un après l'autre, sur un seul modèle local. Il n'y a pas d'astuce qui rende ça plus rapide, et un conseil vaut la peine d'être convoqué exactement quand la réflexion vaut douze tours.

**La fenêtre est partagée équitablement.** Chaque participant qui parle reçoit une part égale de la fenêtre de contexte du modèle — la moitié chacun à deux, le quart chacun à quatre. Cette part doit contenir l'identité propre du participant plus autant du conseil qu'il y rentre. Quand ça approche du plein, enough replie les plus anciennes interventions en une seule ligne chacune, un souvenir d'une ligne de qui a dit quoi : *Plus tôt dans ce conseil : Ed (tour 1) : …*. Le brief n'est jamais replié, et l'intervention à laquelle quelqu'un est en train de répondre non plus — un participant qui ne voit pas la chose à laquelle il répond n'a rien à dire.

Ce repliage est mécanique — il prend la première phrase, il ne demande pas à un modèle de résumer, parce qu'un conseil qui dépense des complétions à se résumer lui-même paie deux fois pour la même fenêtre. Chaque tour signale s'il a replié quelque chose. Quand ça se met à replier tôt et souvent, le remède honnête n'est pas un conseil plus petit, c'est une fenêtre de contexte plus grande dans la fenêtre de modèle (section 15.1) ou un modèle qui a de la place pour ça.


### 18.5 Reconvoquer

Un conseil se conclut, et parfois la question, elle, ne se conclut pas. **reconvoquer**, sur un conseil conclu, en démarre un nouveau à partir de lui : la même assemblée — les mêmes participants avec leurs noms, leurs teintes et leurs charges — les mêmes paramètres, contraintes, sortie souhaitée et plafond de tours, et un brief qui est l'*ancien* brief plus ce que le conseil a réellement produit, posé comme la chose désormais sur la table. Une réponse traverse telle quelle, comme la conclusion ; un document ou une composure traverse comme une référence au fichier et ses deux premiers milliers de caractères. Le nouveau conseil s'ouvre prêt, au tour zéro, sans que personne ait encore parlé.

L'ancien conseil n'est ni rejoué ni réécrit. Son état, ses interventions et sa transcription restent exactement tels qu'ils étaient ; il gagne un lien qui pointe vers son successeur, et le nouveau gagne un lien qui pointe en arrière, pour que la chaîne se lise d'un bout comme de l'autre et qu'aucun bout ne soit une impasse. Un conseil se reconvoque une fois — après ça, le bouton est un lien vers le conseil qu'il est devenu.

---


## 19. Compétences

Une compétence est un paquet de capacité ciblée : un dossier avec un `SKILL.md` (plus des docs de référence et scripts optionnels) qui enseigne à vos readvisors une procédure, un vocabulaire, ou une discipline. Activez les compétences par projet dans la barre latérale. Désactivé veut dire vraiment désactivé — pas du tout dans le prompt — et les nouvelles compétences arrivent désactivées, donc rien ne change dans votre dos. Une compétence non fournie par enough est lue avant même de pouvoir être activée (section 19.9). Tout désactiver est légitime aussi : conversation pure, aucun échafaudage, parfois plus de place pour que le modèle vous surprenne.

### 19.1 analyzer

Quatre modes d'analyse dans une seule compétence.

**Summarize** produit un digest d'une page, équitable, de n'importe quel texte : ce qu'il dit, à qui il s'adresse, la motivation et les biais de l'auteur, le ton, les citations clés.

**Proofread** fait de la correction légère — coquilles, orthographe — sur des documents entiers jusqu'à des livres complets, propulsée par Harper, un correcteur grammatical local à base de règles. Il produit aussi un rapport de correction séparé de suggestions et de constats de phrases répétées, pour que les corrections silencieuses et les appels au jugement restent distinguables.

**Decide** remet votre dilemme à trois personnages archétypaux tirés d'une liste intégrée de dix, qui en débattent pour le compte-rendu. Vous obtenez une recommandation *et* la transcription, pour que vous puissiez peser le raisonnement plutôt que de faire confiance à un verdict.

**Audit** lit quelque chose que vous n'avez pas encore décidé de croire — une compétence que quelqu'un vous a envoyée, un readvisor, un paradigme — et vous dit ce que c'est. D'abord une explication en langage clair de ce que la chose fait réellement et pourquoi vous en voudriez, puis une passe de sécurité : tentatives d'injection de prompt, instructions qui élargissent discrètement la portée d'un readvisor, signaux d'alerte épistémiques, et tout code embarqué, qui reçoit aussi un scan déterministe qui n'implique aucun modèle du tout. Le verdict est l'un de trois mots — **pass**, **flag**, **fail** — appuyé par des constats nommés, jamais un score. C'est en lecture seule : l'audit n'exécute, ne modifie, n'installe, ni n'active jamais la chose qu'il lit.

Les rapports atterrissent dans `rness/io/output/analyzer/audits/<nom-compétence>/` : un `.md` daté que vous pouvez lire comme n'importe quel autre fichier, plus un petit `verdict.json` à côté. Demandez un audit par son nom à tout moment — « vérifie ça avant que je l'active », « qu'est-ce que cette compétence fait vraiment » — et enough exécute aussi ce mode pour vous, sans qu'on le demande, la première fois que vous activez une compétence qu'il n'a pas fournie. Les deux portes écrivent le même rapport dans le même dossier. La section 19.9 raconte cette histoire.

### 19.2 anything-finder

Une équipe de recherche pour les choses qui n'apparaissent pas sur la première page. Trois visages, une seule compétence.

**find** est le visage par défaut, et il porte un plan de match pour chacun des dix types de choses difficiles à trouver, plus un onzième pour les missions qui s'enlisent. **Textes** — livres du domaine public, poèmes, documents historiques. **Vidéo** — films et séries rares, perdus, ou épuisés, avec liens de visionnage et leur légalité précisée. **Images** libres de droits pour une couverture ou un zine. **Produits** — matériel obscur, synthés, instruments, et où en acheter un réellement. **Articles** — l'article coincé derrière un paywall, retrouvé comme sa copie ouverte légitime : preprint, dépôt, archive. **Code** — dépôts sous licence permissive, bibliothèques qui n'ont jamais touché GitHub comprises. **Livres** — des lectures similaires à partir de ce que vous avez déjà adoré. **Audio** — partitions, MIDI, samples, manuels de matériel. **Assets** — polices, textures, modèles 3D, images d'archive. **Données** — jeux de données, API publiques, documents gouvernementaux, archives de journaux.

Les résultats reviennent sous forme de *fiches find* : le lien, pourquoi c'est le bon élément, et — pour tout ce qui touche au droit d'auteur — pourquoi c'est libre d'usage, avec la date de publication ou la licence explicite précisée. Demandez-lui « trouve-moi une édition du domaine public de *The Moonstone* assez propre pour être composée », « où puis-je légalement regarder la version de 1974 », « existe-t-il une bibliothèque sous licence MIT qui fait ça ». Les réponses honnêtes font partie du contrat : « ça existe mais n'est pas légalement disponible » et « trois candidats, je suis à 70 % sur le deuxième » sont de vrais résultats ici, et là où la seule route est un site de piratage, il le dira et vous orientera plutôt vers la bibliothèque, le système de prêt, ou la boutique.

**patents** est le visage antériorité. Donnez-lui une invention et il lance une recherche de nouveauté structurée à travers les brevets accordés, les demandes publiées, et la littérature non-brevet, puis rapporte ce qu'il a trouvé et ce que ça signifie pour la nouveauté et la non-évidence — avec un avertissement « ceci n'est pas un conseil juridique » qui reste dans chaque rapport, parce que c'est exactement ce que c'est. « Ça a été breveté ? » « Antériorité sur un antivol de vélo magnétique qui… » « Mon idée est-elle brevetable ? » Les bases de données qu'il n'a pas pu atteindre reviennent étiquetées *non vérifié*, jamais discrètement comme *vide*.

**venture** est le visage « est-ce que c'est un business ? », et il compose les deux autres. Un balayage de marché pour ce qui existe déjà, une vérification d'antériorité, et une passe de paysage concurrentiel sur les entreprises, les alternatives open-source, les produits adjacents, et le cimetière de ceux qui ont essayé et fermé. Ce que vous obtenez, c'est une lecture équitable — ce qui est encombré, ce qui est adjacent, ce qui est réellement ouvert, et l'angle d'attaque que les preuves soutiennent réellement — suivie du meilleur argument *pour* et du meilleur argument *contre*, chaque point ancré à un lien, et une courte liste de questions auxquelles vous seul pouvez répondre. Demandez-lui « devrais-je construire ça », « est-ce que ça existe déjà comme produit », « où est le vide de marché ici ». Il ne notera pas votre idée, n'écrira pas votre business plan, et ne vous dira pas de lever des fonds. Et il traite un champ vide comme une question, pas comme un feu vert.

La sortie va dans `rness/io/output/anything-finder/`. Tout ce qu'il récupère passe par le broker comme n'importe quel autre accès web, donc un domaine hors liste blanche est routé via Tor — et quand une source refuse de répondre, le rapport nomme l'hôte et vous dit quoi ajouter à `allowlists.md`, plutôt que de laisser un trou silencieux dans les résultats.

### 19.3 girraph-merirmaid

La compétence de discipline pour les deux primitives de diagramme d'enough (sections 20 et 21). La moitié girraph enseigne une cartographie IBIS correcte : une question par tour, pas de saut aux solutions, votre confirmation comme règle d'arrêt. La moitié merirmaid porte les règles de rédaction Mermaid, comme garder des étiquettes de nœud assez courtes pour que vous puissiez les modifier confortablement. Les modes fonctionnent sans la compétence ; avec elle, votre readvisor devient un partenaire de cartographie véritablement discipliné.

### 19.4 lexicographer

Le style maison du dictionnaire (section 13), remis à votre readvisor. Votre readvisor en chef peut chercher des mots et les ajouter à votre propre dictionnaire quand cette compétence est désactivée — le dictionnaire est toujours à portée — mais activée, tout le guide colonne par colonne voyage à chaque tour : comment s'écrit une prononciation (API américain large, accent marqué), auquel des 45 domaines de FEED appartient un mot, comment se formule un premier emploi (« late 18th century », « 2010s »), ce que signifient les bandes de fréquence, où vont les points de syllabes. Elle porte aussi la forme de la conversation — chercher d'abord, rédiger ce qui peut l'être, demander ce que vous seul pouvez répondre, relire, et n'ajouter qu'avec votre oui — de sorte qu'un mot que votre famille dit depuis vingt ans ressorte comme s'il avait toujours été dans le livre.

Demandez-lui « *flumpet*, c'est un mot ? », « ajoute *glimmerwick* à mon dictionnaire », « ma version de *draft*, s'il te plaît ». Elle n'est pas faite pour traduire du texte — c'est `translator` — et ce n'est pas un correcteur ; ça, c'est analyzer.

### 19.5 memoir-dialectic

Un collaborateur de mémoires patient, sur plusieurs sessions. Il vous interroge — une ou deux questions à la fois, jamais un déluge — et classe tout : des documents de plan numérotés dans l'ordre de la conversation, un index pour reprendre rapidement, un fichier de notes pour les vidages de cerveau désordonnés, et finalement une synthèse de plan et, seulement si vous le voulez, des brouillons. Le dossier, c'est la mémoire. Vous pouvez disparaître pendant des semaines ou des années et il reprend là où vous vous étiez arrêté. Construit pour toute la gamme, de l'histoire de vie complète à un seul jalon, avec une gestion explicite des sujets sensibles et des zones interdites, et une préservation soigneuse de votre propre façon de vous exprimer — la voix compte, surtout si un brouillon approche.

### 19.6 readvisory

La compétence qui fabrique un readvisor (section 17), en interrogeant une personne plutôt qu'en rédigeant une spécification.

Deux façons de récolter. **En direct** : elle vous interroge *vous*, patiemment, une ou deux questions à la fois, douze à dix-huit en tout, sur la façon dont vous décidez réellement le genre de chose qu'on va demander à ce readvisor. **Par questionnaire** : elle écrit un fichier simple, prêt à envoyer par courriel, que vous adressez à quelqu'un dont vous aimeriez avoir le jugement sous la main — un ami, un mentor, un ancien rédacteur en chef, un parent — qui y répond à son rythme, et vous recollez les réponses quand elles arrivent. Un questionnaire peut dormir une semaine dans une boîte de réception : tout le travail est donc suivi dans un fichier de requête (section 8.3) qu'une séance des semaines plus tard peut reprendre à froid.

Les deux voies se terminent de la même manière : une courte passe de relance vers *vous* (l'étape qui rend un readvisor meilleur qu'une transcription), puis les deux documents rédigés et soumis à votre correction ligne par ligne, et alors seulement, avec votre feu vert, installés — dans ce projet, ou dans `~/enough/readvisors/` où tous les projets de la machine les voient. Les deux documents sont lus par le même scan de sécurité qu'une compétence téléchargée subit avant que quoi que ce soit ne soit écrit, et l'interrupteur **forge new readvisors** du broker (section 9) décide si la dernière étape revient à enough ou à vous.

Elle a une idée claire de ce à quoi elle ne sert pas. Elle ne renommera pas votre readvisor en chef et ne convoquera pas de conseil : elle fabrique les participants, elle ne tient pas la réunion.

### 19.7 scaffold

Transforme un tas de réflexion en une structure que vous pouvez regarder.

Donnez-lui un vidage de cerveau — collé dans le panneau, un fichier du projet, ou une composure qui existe déjà — et elle lit pour la forme plutôt que pour les phrases. Elle connaît les formes de récit (arcs, temps forts, fils de continuité, dénouements, fins), les formes d'argumentation (thèse, fondements, garantie, contre-thèse, chute) et les formes de plan (objectif, phases, dépendances, risques, critères de fin). Elle pose deux questions de clarification au maximum, souvent aucune, puis passe le résultat à enough, qui le dispose en composure : une carte par temps fort, par section ou par phase, groupées en colonnes ou en rangées, sur le canevas devant vous (section 4.5).

La règle qui la rend précieuse : **elle n'invente jamais de matière pour boucher un trou.** Là où la structure a besoin de quelque chose que vous n'avez pas écrit, elle écrit une carte `[gap: …]` à la place — teintée en orangé, gardant la question — pour que la forme vous montre ce que vous lui devez encore. Une histoire dont vous connaissez la fin mais pas le retournement reçoit une carte de trou qui dit exactement ça, et c'est en général la carte la plus utile du tableau.

Elle n'écrit pas le texte. Elle écrit la structure, et chaque carte posée dessus est à vous dès l'instant où elle atterrit.

(Un seul nom, deux choses, et ça vaut le coup de les séparer une bonne fois : les *scaffolds* que génère le paradigme text-planning — section 16.1 — sont des guides structurels par section, écrits en markdown, que vous étoffez ensuite en prose. Cette compétence-ci produit une composure entière. Les deux s'entendent bien ; un plan construit en text-planning fait un bon vidage de cerveau à donner à celle-ci.)

### 19.8 translator

Traduction hors ligne à travers environ 419 langues via MADLAD-400 — un téléchargement unique d'environ 3 Go qui tourne sur CPU ou Apple Silicon et ne rentre jamais téléphoner à la maison. De courtes phrases à des documents entiers, des langues majeures aux langues à faibles ressources et indigènes. Traduisez une lettre, localisez un README, vérifiez ce que veut dire un passage, faites l'aller-retour d'une phrase à travers une troisième langue comme test de préservation du sens — tout ça avec le réseau débranché. Pour certaines langues à faibles ressources, un moteur optionnel NLLB-200 offre une meilleure qualité ; il porte une licence non commerciale, donc c'est optionnel via le paradigme translation.

### 19.9 Écrire les vôtres, et faire confiance à celles des autres

Les huit ci-dessus sont des démonstrations. Le *mécanisme* de compétence — des instructions markdown, chargées quand activées, avec une `description:` qui dit à un readvisor quand s'engager — est la vraie fonctionnalité. Guides de style maison, checklists de domaine, formats de rapport récurrents, procédures de traitement de données : si vous pouvez décrire une compétence en prose, vous pouvez la remettre à vos readvisors comme une compétence. Construisez la vôtre avec workflow-design (section 16.3), ou forkez l'une des huit et faites-la vôtre.

L'autre bout de cette boucle, ce sont les compétences qui arrivent d'ailleurs. Une compétence, ce sont des instructions que vos readvisors vont suivre, ce qui veut dire qu'une compétence venue d'internet mérite exactement autant de méfiance que n'importe quel autre fichier venu d'internet. Alors enough les lit pour vous :

- **Ce qu'enough fournit d'origine est de confiance, et ça se voit comme toujours.** Les huit ci-dessus arrivent comme des liens vers les défauts propres de l'installation. Elles s'activent instantanément. Rien ne les audite.
- **Tout le reste est désactivé tant que ça n'a pas été lu.** Déposez un dossier de compétence dans `rness/skills/` — téléchargé, envoyé par un ami, décompressé d'un `.skill` — et il reste là désactivé, marqué *unverified* dans la barre latérale. La première fois que vous l'activez, enough fait tourner le mode audit d'analyzer dessus (section 19.1) avant qu'un seul mot n'atteigne un readvisor. Vous voyez ça se passer dans la ligne : *unverified* → *auditing…* → *audited*.
- ***Flagged* veut dire pas activé.** Si l'audit trouve quelque chose, la ligne dit *flagged* (ou *failed*), la compétence reste désactivée, et vous obtenez deux boutons : **read report** ouvre le rapport complet dans la vue de lecture, et **activer quand même** vous demande de confirmer puis enregistre la décision comme étant la vôtre — le constat n'est pas effacé, il est outrepassé, et la ligne affiche dès lors *trusted by you*. L'audit conseille. Vous décidez. (Si vous préférez travailler dans le fichier, modifier le `verdict.json` de cette compétence en `"verdict": "pass"` fait la même chose.)
- **Modifiez une compétence et elle est relue.** L'audit est lié aux octets exacts qu'il a lus — noms de fichiers et contenus, les deux. Changez n'importe quoi et la prochaine fois que vous activez cette compétence, elle est réauditée. Ça inclut une que vous auriez précédemment activée quand même : une dérogation décrit un ensemble particulier de fichiers à un moment particulier, et elle ne survit pas à une modification.
- **Une compétence écrite pour vous au cours d'une séance compte aussi comme non vérifiée.** C'est délibéré, pas un oubli. Quand workflow-design écrit un nouveau `SKILL.md` dans `rness/skills/`, enough audite ce devoir à la première activation. C'est quasi instantané quand il n'y a rien à trouver.
- **Sans modèle en cours d'exécution, un audit ne peut pas se terminer** — et il le dit, en signalant que « the llm half of the audit couldn't run » plutôt que de laisser passer la compétence. Activez un modèle et réactivez-la, ou utilisez **activer quand même** si vous savez déjà ce qu'il y a dedans.

Les rapports vivent dans `rness/io/output/analyzer/audits/<nom-compétence>/` — le même dossier où analyzer écrit quand vous demandez un audit en conversation. Deux portes, un document, et c'est un fichier markdown ordinaire que vous pouvez ouvrir, garder, ou supprimer.

---

## 20. Le mode girraph et l'extension `.girraph`

Ça se prononce comme *graph*. Le « ir » est silencieux — il représente *iterative* et *recursive* (itératif et récursif). L'animal est un 🦒, et l'animal aussi est silencieux.

Un girraph est la carte d'une question difficile. Pas une liste de tâches : l'image d'un *désaccord*, y compris ceux, productifs, que vous avez avec vous-même. Certains problèmes (« Devrions-nous faire l'école à la maison ? », « De quoi parle vraiment ce livre ? », « Prenons-nous le financement ? ») font pousser une objection à chaque réponse et une nouvelle question sous chaque objection. Une liste enterre ce combat. Un girraph le garde visible :

- ❓ **issues** (questions) — des questions ouvertes, toujours formulées comme des questions
- 💡 **positions** — des réponses possibles
- ➕ ➖ **arguments** — des raisons pour et contre une position
- 📄 **notes** — contexte, contraintes, références à des documents
- 🦒 **girraphs imbriqués** — une sous-question assez grosse pour sa propre carte

La filiation, c'est IBIS, une méthode des années 1970 pour les « problèmes pervers » — le genre sans réponse propre ni point d'arrêt naturel. Le girraph est la version texte brut qu'en fait enough.

Le format est un fichier texte se terminant en `.girraph`, une ligne par pensée, lisible dans n'importe quel éditeur en 2026 comme en 2056 :

```
%girraph 0.1
title: Should enough ship a plugin API?

q1 ? Should enough ship a plugin API?
p1 ! Ship a minimal one < q1
a1 + Ecosystem growth needs stable hooks < p1 by:graham
a2 - API surface = forever maintenance < p1 by:open-skeptic
```

`< q1` veut dire « ceci répond à q1 » ; `by:` retient à qui appartient l'affirmation. Aucune base de données, rien de caché. Le fichier, c'est la carte.

Dans l'application, cliquer sur un `.girraph` ouvre le mode girraph : un arbre repliable que vous modifiez directement. Cliquez sur une étiquette pour la réécrire. Survolez une ligne pour les boutons ajouter, lier, et supprimer. Cliquez sur une puce 🦒 pour descendre dans une carte imbriquée — un fil d'ariane vous ramène — et cliquez sur une puce 📄 pour lire un document référencé sur place. En discussion, dites « girraph-moi ça » ou « cartographie ça », et votre readvisor modifie le même fichier à travers les mêmes opérations au niveau du nœud que vous utilisez, si bien que vous pouvez travailler la carte tous les deux à la fois. Supprimer des nœuds exige toujours votre confirmation, et les enfants ne sont jamais orphelins en silence.

Un girraph peut aussi faire pousser un **mirror merirmaid** : un clic sur le bouton merirmaid dans la barre d'outils du girraph crée un diagramme Mermaid lié, à régénération automatique, de la carte — les issues en hexagones, les positions en stades, les soutiens et objections tracés dans leurs couleurs — qui se garde à jour tout seul à mesure que le girraph change. Cartographiez en girraph, jetez un œil en merirmaid.

Trois habitudes font marcher les girraphs. Formulez les issues comme des questions (« Comment finance-t-on l'année deux ? », pas « le problème d'argent »). Attachez les arguments aux positions, pas aux issues — les raisons sont des raisons pour ou contre une *réponse*. Et séparez une branche dans son propre fichier avant qu'elle ne s'étale. Activez la compétence girraph-merirmaid et votre readvisor vous tiendra aux trois.

---

## 21. Le mode merirmaid et l'extension `.merirmaid`

Là où un girraph cartographie un argument, un **merirmaid** dépeint une structure. Un fichier `.merirmaid` est un diagramme [Mermaid](https://mermaid.js.org/) — organigramme, diagramme de séquence, machine à états, diagramme ER, tout ce que Mermaid dessine — avec un petit en-tête de frontmatter, rendu en direct dans le navigateur. En local, bien sûr ; pas de CDN, comme tout dans enough.

Deux modalités, déclarées dans l'en-tête :

- **wip** — un tableau blanc de travail. Cliquez sur le texte de n'importe quel nœud et modifiez l'étiquette sur place, avec un compteur de caractères en direct ; les changements structurels (ajouter une boîte, recâbler une flèche) passent par votre readvisor — demandez dans le panneau. Demandez un diagramme de votre pipeline, de votre intrigue, de votre organisation, et votre readvisor écrit la source, le navigateur le dessine, et vous ajustez les mots.
- **mirror** — un reflet en lecture seule d'une structure qui vit ailleurs : le contenu d'un cachebox (section 12.1) ou un girraph (section 20). Les mirrors se régénèrent quand leur source change. Pour changer l'image, changez la chose.

Les diagrammes se relient. Un nœud peut pointer vers un autre `.merirmaid`, un `.girraph`, ou un document markdown, et cliquer dessus vous y emmène, un fil d'ariane marquant le chemin du retour — si bien qu'un ensemble de diagrammes devient un atlas navigable de votre projet. Et quand un diagramme a une erreur de syntaxe, le mode merirmaid montre l'erreur plus la source brute plutôt qu'un panneau vide. Il y a toujours quelque chose à partir de quoi corriger.

La compétence girraph-merirmaid (section 19.3) porte la discipline de rédaction pour les deux types de fichier. Une règle de base qui en vient mérite d'être répétée ici : si le premier geste honnête est de poser une question, vous voulez un girraph ; si c'est de dessiner une boîte et une flèche, vous voulez un merirmaid.

---

## 22. Où aller à partir d'ici

Le moyen le plus rapide de faire d'enough le vôtre :

1. Lancez-le dans un vrai projet — quelque chose qui vous tient vraiment à cœur.
2. Passez une session à discuter, et laissez le profil du projet commencer à s'accumuler.
3. Modifiez `MOTIVATION.md` pour dire à quoi sert réellement le projet.
4. La première fois que vous répétez une instruction, arrêtez-vous. Mettez-la plutôt dans `AGENT.md`.
5. La première fois que votre travail prend une forme que les défauts ne couvrent pas, dites « concevons un paradigme pour ça » — ou une compétence, ou un readvisor — et laissez workflow-design vous guider.

Cette boucle — remarquer la friction, coder le correctif, continuer à travailler — c'est tout le jeu. Les composants intégrés vous font démarrer. Le système avec lequel vous finissez, personne ne le fournit. Vous l'écrivez.

---

*enough est © 2026 Graham Smith, distribué sous licence Apache License 2.0. Le texte propre du dictionnaire — les mots de FEED, ses définitions et le reste — est © 2026 Graham Smith lui aussi, mais il n'est pas sous cette licence : il est livré pour être utilisé dans enough, tous droits réservés pour l'instant. Le contenu Wikipédia atteint via wikisink est en CC BY-SA. Ce document : à vous de le modifier aussi.*
