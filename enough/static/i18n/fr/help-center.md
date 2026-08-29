Bonjour, ici Graham, le créateur d'enough. Ce document -- à part ce passage-ci, je veux dire -- est écrit et maintenu principalement par des agents. Je vais presque certainement y glisser quelques grahamismes de temps à autre, mais l'idée est de ne pas laisser mon propre désir d'écrire des trucs amusants prendre le pas sur une documentation complète.

# le centre d'aide d'enough

> Tout ce que vous pouvez faire avec enough, en un seul endroit. Rédigé pour enough **0.3.0**, incluant l'écran d'accueil (tous les projets que vous avez jamais démarrés, dans une seule liste, avec une porte d'entrée et une porte de sortie — section 2), la passe de conversion (PDF, documents Word, ebooks, présentations et classeurs qui s'ouvrent comme des jumeaux markdown modifiables, avec export, synchronisation, et une visionneuse d'image — section 6), la passe des compétences (le nouveau mode audit d'analyzer, la compétence `anything-finder`, et l'audit au premier usage qui lit toute compétence non fournie par enough avant de l'autoriser), la passe d'août 2026 (sept modèles locaux avec des installations à faisabilité vérifiée, et **enough.app** — l'application de bureau signée et notariée), la passe d'interface de juillet 2026 (la pile de modes, les bulles d'aide par dossier, les reflets girraph→merirmaid), et la passe de préférences 0.3.0 (mise à l'échelle de l'ui et du texte par projet, et l'interface + l'aide en six langues — section 9). Là où ce document et l'application devant vous ne sont pas d'accord, c'est l'application qui a raison et ce document qui a un bug — les corrections sont bienvenues sur [enough.support](https://enough.support).

enough est un système de langage personnel qui tourne sur votre propre machine. Vous le pointez vers un dossier, vous lui parlez, et il vous aide à planifier, écrire, réviser, chercher, et traduire. Les modèles sont locaux par défaut. Vos fichiers restent les vôtres. Et presque tout ce que vous le verrez faire est défini dans de simples fichiers markdown que vous pouvez ouvrir, lire, et modifier.

Gardez une idée en tête pendant votre lecture : **les fonctionnalités intégrées de ce manuel ne sont qu'une fraction de ce qu'enough peut faire.** Les paradigmes, rôles et compétences fournis d'origine sont un kit de démarrage — des exemples fonctionnels de trois mécanismes de personnalisation, pas leurs limites. Le but ultime, c'est que vous écriviez les vôtres, ou que vous les fassiez écrire par l'agent avec vous : un paradigme pour votre façon de planifier des essais, un rôle qui argumente comme votre lecteur le plus coriace, une compétence qui code votre style maison. La section 3 explique comment. C'est la section la plus importante de ce document, et le manuel n'arrêtera pas de vous y renvoyer.

---

## 1. Installation, raccourcis, et cette documentation

### 1.1 Ce dont vous avez besoin

- Un Mac avec Apple Silicon. (enough est construit et testé sur macOS. Le support Linux est prévu ; Windows est envisageable.)
- De l'espace disque pour au moins un modèle — le plus petit fait environ 5 Go.
- Aucun compte, aucune clé API, aucun abonnement. À moins que vous n'optiez plus tard pour l'emplacement de modèle cloud (section 13.2), tout tourne en local.

### 1.2 Installation

Deux portes, une seule maison.

**L'application — la voie courte.** Téléchargez le DMG `enough` depuis la page des releases, ouvrez-le, glissez **enough** dans Applications, et lancez. macOS signalera qu'il s'agit d'une application venue d'internet — elle est signée et notariée, donc c'est la sympathique boîte de dialogue bleue avec un bouton **Ouvrir**, une seule fois, pas un avertissement à contourner. Un guide de premier lancement prend le relais : il construit son propre environnement Python, vous montre la liste des modèles avec un verdict honnête sur ce qui tient sur *cette* machine (section 13.1), liste les extras optionnels que vous avez déjà, et vous remet à l'écran d'accueil pour choisir le dossier dans lequel vous voulez travailler (section 2). L'essentiel de l'attente, c'est le téléchargement des modèles. Pas de Terminal, pas de Homebrew, pas de git.

L'application embarque son propre moteur d'inférence et Python. Les extras optionnels — saisie vocale, récupération de pages web, vérification grammaticale, traduction — restent des programmes séparés ; la page Extras du guide nomme chacun d'eux, ce qui se désactive sans lui, et comment l'obtenir. Rien n'est obligatoire, et rien ne s'installe dans votre dos. Un extra n'est même pas un programme séparé du tout : la **lecture de PDF** s'installe depuis l'intérieur d'enough quand vous le voulez (section 6.8).

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
6. Télécharger les poids des modèles. Chaque modèle pris en charge est proposé un par un, avec sa taille et une vérification de faisabilité par rapport à la mémoire et à l'espace disque libre de votre machine — ✓ veut dire confortable, ~ veut dire juste, ✗ veut dire cherchez ailleurs. Dites oui à autant ou aussi peu que vous voulez ; la section 13.1 les décrit tous, et tout ce que vous sautez reste une installation en un clic plus tard.
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

puis rendez-vous sur `http://127.0.0.1:3456` (enough l'ouvre pour vous). Dossier différent, projet différent, mémoire d'agent différente. Le seul dossier depuis lequel vous ne pouvez pas lancer, c'est `~/enough/` lui-même — la CLI refuse, parce que c'est l'installation, pas un projet.

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

- **L'aide intégrée** — les bulles `(?)` disséminées dans l'interface, chacune expliquant ce à quoi elle est attachée : un *what*, un *how*, et une liste *ideas*. Voir la section 9.6.
- **Les aide-mémoires** — raccourcis clavier et syntaxe markdown, à un clic dans la fenêtre UI. Voir la section 9.5.
- **[enough.support](https://enough.support)** — le forum communautaire : aide à l'installation, partage de flux de travail, et des gens qui vous aideront volontiers à construire les personnalisations vers lesquelles ce manuel n'arrête pas de vous pousser.

Et tout ça — ce manuel, les bulles, l'interface qui les entoure — se lit en six langues : anglais, français, espagnol, allemand, chinois, et japonais. La section 9.4 présente le menu déroulant et les petits caractères.

---

## 2. L'écran d'accueil

Avant d'être dans un projet, vous êtes sur **l'accueil** : un seul cadre listant tous les dossiers que vous avez jamais transformés en projet enough, plus une tuile pour en ajouter un autre. C'est délibérément l'écran le plus tranquille de l'application. Pas de discussion, pas de barre latérale, pas de modèle, pas d'agent — rien ne tourne encore et rien n'est en train d'être pensé. Juste vos projets, et le bouton UI ⚙ dans la barre supérieure pour le thème et ce manuel.

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

Ces trois colonnes du milieu sont les trois mêmes indicateurs qu'enough affiche dans la barre supérieure quand vous avez un document ouvert — ¶ pour les paragraphes (blocs séparés par une ligne vide), W pour les mots, C pour les caractères, espaces et sauts de ligne compris — additionnés sur tout le projet. La règle sur *quels* fichiers sont comptés vaut une phrase, parce que c'est elle qui donne du sens aux chiffres : tout fichier markdown que l'arborescence du projet vous montrerait elle-même, **y compris les jumeaux des documents convertis** (un `.docx` que vous éditez ici, c'est votre écriture), et **rien** de ce qui est à l'intérieur de `rness/` (l'échafaudage de l'agent n'est pas votre livre). Donc le chiffre dans la colonne W, c'est assez précisément la quantité de ce que vous avez écrit.

Cliquez sur n'importe quel en-tête de colonne pour trier selon elle ; cliquez à nouveau sur le même pour inverser. Les projets qui n'ont rien à rapporter — jamais ouverts, jamais comptés — coulent vers le bas dans tous les cas plutôt que de se faire passer pour les plus anciens. L'ordre par défaut est du plus récemment modifié au moins récent.

Un projet dont le dossier n'est pas là en ce moment — un disque externe débranché, un dossier que vous avez déplacé dans Finder — s'affiche grisé, avec le chemin dont il se souvient dans l'infobulle. Il n'est **pas** retiré de la liste, et il garde les chiffres qu'il avait la dernière fois que vous l'avez vu. Un projet sur un disque dans un tiroir n'est pas un projet que vous avez perdu.

### 2.2 Cliquer sur un projet : la carte

Un simple clic n'ouvre pas un projet. Il vous dessine une **carte** de celui-ci : un diagramme merirmaid en lecture seule (section 18) du contenu visible du dossier, avec un petit nœud d'information en haut portant le chemin, le nombre de fichiers, les totaux ¶ et W, et les dates de création, dernière ouverture et dernière modification du projet. C'est le même genre d'image que cacheawl dessine pour un cachebox (section 11.1), pointée sur un projet à la place.

La carte sert pour le moment où vous avez quatre dossiers aux noms plausibles et voulez savoir lequel contient les chapitres. Regardez, puis décidez.

Une fois décidé, le bouton **ouvrir le projet** de la barre d'outils l'ouvre. Esc, ou le ruban en haut à droite, vous ramène à la grille. Et si vous saviez déjà lequel vous vouliez, **double-cliquez** sur la tuile ou la ligne et elle s'ouvre sans détour.

L'ouverture se ressemble dans les deux cas : le chargeur apparaît une seconde ou deux pendant qu'enough éteint l'écran d'accueil et démarre le projet à sa place, et vous voilà dans la vue de discussion (section 4) exactement comme si vous aviez lancé directement dans ce dossier.

### 2.3 Ajouter un dossier

La dernière tuile de la grille — celle avec le plus — c'est comme ça qu'un dossier devient un projet.

Cliquez dessus et macOS ouvre son propre sélecteur de dossier. Choisissez n'importe quel dossier de notes, de brouillons, ou de documents ; enough y ajoute `rness/` (section 7), l'enregistre sur votre écran d'accueil, et l'ouvre. La tuile affiche *en attente du sélecteur de dossier…* pendant que la boîte de dialogue est ouverte, alors prenez tout le temps que vous voulez pour naviguer.

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

**Partout, application ou navigateur :** le bouton **fermer le projet → accueil** en haut de la fenêtre UI ⚙ (section 9). Il demande d'abord, parce que fermer met fin à la session — la conversation devant vous est terminée, comme elle le serait en quittant — et vous dépose ensuite exactement au même endroit que le ferait ⌘W.

Ni l'un ni l'autre ne touche votre dossier. Vos fichiers, votre `rness/`, vos fichiers de requête, et vos journaux de session sont tous exactement là où vous les avez laissés ; seule la conversation en cours se termine.

Une conséquence du nouveau ⌘W qui vaut la peine d'être connue si vous utilisez enough depuis un moment : **⌘W ne ferme plus la fenêtre.** enough est une application à une seule fenêtre et fermer cette fenêtre la quitte, donc ⌘Q et le bouton rouge couvraient déjà ce terrain, et ⌘W avait un meilleur travail à faire.

Et une interaction entre ceci et le réglage de réouverture, parce que sinon ça vous surprendra exactement une fois : **fermer un projet ne fait pas oublier ce projet à enough.** Si **Rouvrir le dernier projet au lancement** est activé et que vous fermez un projet, restez un moment sur l'accueil, puis quittez — le prochain lancement rouvre ce projet, pas l'accueil. L'interrupteur est le réglage qui décide où vous commencez ; Fermer le projet est le bouton qui décide où vous êtes maintenant. Si vous voulez désormais commencer sur l'accueil, désactivez l'interrupteur.

### 2.6 Ce que l'accueil retient

Trois petites choses, toutes globales à la machine — elles vous suivent de projet en projet et retour à l'accueil, et elles ne sont stockées dans aucun dossier de projet :

- **Le thème et la police** (section 9.1). L'accueil porte ce que vous avez choisi en dernier, et un thème vers lequel vous basculez *sur* l'écran d'accueil est le thème dans lequel votre projet s'ouvre. C'est celui qui avait l'habitude d'agacer les gens : l'écran de lancement et l'écran de travail sont désormais d'accord, toujours.
- **Icônes ou liste**, de la section 2.1.
- **Si les projets masqués sont affichés**, de la section 2.4.

Tout le reste à propos d'un projet vit dans le dossier de ce projet, où vous pouvez le lire.

---

## 3. Personnalisation du flux de travail à un niveau fondamental

Si vous ne lisez qu'une section, lisez celle-ci.

La plupart des logiciels vous donnent des fonctionnalités. enough vous donne des mécanismes. La personnalité, la méthode et le jeu de compétences de l'agent sont assemblés à neuf à chaque message à partir de fichiers markdown posés sur votre disque :

- **`AGENT.md`** — qui est l'agent et comment il opère (section 4.1)
- **`MOTIVATION.md`** — le pourquoi : valeurs, priorités, ce à quoi ressemble « terminé »
- **Les politiques** — des règles strictes sur ce qu'il peut lire, écrire, et récupérer (section 4.2)
- **Le paradigme actif** — le cadre de raisonnement en vigueur en ce moment (section 14)
- **Les compétences activées** — des capacités auxquelles il peut faire appel (section 16)
- **Les rôles activés** — d'autres personnages que vous pouvez convoquer (section 15)
- **Le profil du projet** — ce qu'il a appris sur ce projet (section 7.1)

Modifiez n'importe lequel de ces éléments, dans l'application ou dans n'importe quel éditeur de texte, et le changement prend effet au message suivant. Pas de recompilation, pas de redémarrage, pas d'API de plugin. Si vous savez écrire un fichier markdown, vous savez reprogrammer votre agent.

### 3.1 Global contre local au projet

Tout ce qui est personnalisable suit un seul motif : **les défauts vivent dans `~/enough/defaults/`, les projets s'y lient, et n'importe quel projet peut rompre le lien.**

Modifiez un fichier dans `~/enough/defaults/` et tout projet encore lié à lui récupère le changement. Dans un projet, ouvrez un fichier lié et cliquez sur **personnaliser** — le lien devient une copie locale au projet, et à partir de là ce projet fait sa propre route pendant que les autres continuent de suivre le défaut global. L'arborescence des fichiers vous dit lequel est lequel d'un coup d'œil : les fichiers liés s'affichent *en italique et atténués*, les copies locales s'affichent normalement.

Les nouvelles compétences, nouveaux rôles et nouveaux paradigmes déposés dans `~/enough/defaults/` apparaissent dans tous les projets au lancement suivant. Les compétences et les rôles arrivent désactivés, donc rien ne change dans votre dos ; vous les activez par projet quand vous les voulez. Une compétence qu'enough n'a pas fournie — une que vous avez téléchargée, une qu'un ami vous a envoyée, une que votre propre agent a écrite pour vous — est lue avant d'être autorisée à entrer. La section 16.6 couvre ce sujet.

### 3.2 Les trois types de composants

| | Paradigme | Compétence | Rôle |
|---|---|---|---|
| Ce que c'est | Un cadre de raisonnement — comment l'agent aborde le travail | Une capacité ciblée — vocabulaire, recettes, procédures | Un second personnage que vous pouvez convoquer — son propre AGENT.md + MOTIVATION.md |
| Combien actifs | Exactement un à la fois | N'importe quel nombre activé | N'importe quel nombre activé |
| Vit à | `rness/paradigms/<nom>.md` | `rness/skills/<nom>/SKILL.md` | `rness/roles/<nom>/` |
| Exemples fournis | default, text-planning, translation, workflow-design | analyzer, anything-finder, girraph-merirmaid, memoir-dialectic, translator | block-breaker, open-skeptic |

### 3.3 Construire les vôtres

Vous pouvez écrire ces fichiers à la main — ce sont du markdown avec un petit bloc YAML en tête — mais vous n'êtes pas obligé. Le **paradigme workflow-design** fourni d'origine (section 14.4) existe pour que l'agent puisse les construire avec vous. Dites « construis-moi une compétence qui… » ou « crée un rôle qui… » ou « fais-moi un paradigme pour… » et l'agent bascule vers workflow-design, pose ses questions de clarification (périmètre ? nom ? conditions de déclenchement ? fichiers compagnons ?), et écrit le composant correctement, frontmatter `description:` comprise, celle qui indique aux tours futurs quand y faire appel.

Ce que les gens construisent réellement :

- Un **paradigme** pour chaque mode distinct de leur travail — recherche, rédaction, révision — avec des règles explicites pour savoir quand changer.
- Une **compétence** qui code la voix d'une newsletter, un format de citation, la terminologie d'une thèse.
- Un **rôle** qui est un canard en plastique posant des questions socratiques, ou un relecteur sceptique, ou un expert du domaine construit à partir de vos propres fichiers de connaissance.

Le reste de ce manuel décrit les composants intégrés. Lisez chacun d'eux comme un exemple travaillé que vous avez le droit de copier, forker, et améliorer.

---

## 4. Discussion avec l'agent — la base de la pile

Ouvrez un projet et vous atterrissez dans la vue de discussion : la conversation avec votre agent, plus la barre latérale montrant votre projet. C'est le rez-de-chaussée. Chaque autre mode s'empile par-dessus et finit par se refermer jusqu'à lui. (L'*écran d'accueil* de la section 2 est une tout autre chose — c'est là que vous êtes avant qu'un projet soit ouvert ; ici, c'est là que vous êtes une fois qu'il l'est.)

Ce qu'on trouve ici :

- **La discussion.** Tapez un message, appuyez sur ⌘Enter (ou le bouton envoyer). Les réponses arrivent en direct, et l'agent peut agir pendant qu'il parle — lire et écrire des fichiers, exécuter des commandes shell, récupérer des pages — chaque appel d'outil apparaissant dans la transcription au fur et à mesure.
- **Le bouton micro.** Cliquez dessus et dictez. La parole est transcrite localement par whisper.cpp ; votre voix ne quitte jamais la machine. Le bouton pulse pendant l'enregistrement. Cliquez à nouveau pour arrêter.
- **La barre latérale.** L'arborescence de fichiers du projet, plus les sections de contrôle : le **paradigme** actif, les interrupteurs pour les **compétences** et les **rôles**, et vos **requêtes**. Option-cliquez sur n'importe quel fichier ou dossier pour un menu contextuel (nouveau fichier, nouveau dossier, copier le chemin, copier le nom). ⌘\ masque et affiche toute la barre latérale.
- **La barre supérieure.** Des boutons pour la fenêtre de modèle, le broker, la fenêtre UI, wikisink (🚰), et cacheawl — et au bord droit, les indicateurs pour les modes actuellement empilés et ouverts (section 12).

### 4.1 AGENT.md et MOTIVATION.md

Chaque projet porte sa propre copie de ces deux fichiers dans `rness/`. Ils sont la racine de l'identité de l'agent, et tous deux sont chargés à chaque tour.

**`AGENT.md`** est le *how* (comment) : les instructions de travail. Ton, garde-fous, conventions, consignes permanentes. « Gardez la prose en minuscules. » « Ne touchez jamais aux fichiers dans `archive/`. » « Demandez avant d'exécuter des commandes shell de plus d'une ligne. »

**`MOTIVATION.md`** est le *why* (pourquoi) : les valeurs et priorités au-delà de la tâche qui se présente. À quoi sert le projet, qui il sert, quels compromis comptent (l'exactitude plutôt que la vitesse ? la concision plutôt que l'exhaustivité ?), à quoi ressemble « terminé ».

Cliquez sur l'un ou l'autre fichier dans la barre latérale pour le lire ; appuyez sur **personnaliser** pour forker votre copie locale au projet, ou modifiez-le dans n'importe quel éditeur de votre choix. Les changements arrivent au message suivant. Les rôles utilisent le même motif à deux fichiers (section 15) — l'agent principal n'est pas spécial, juste premier.

### 4.2 Le dossier des politiques et les listes blanches

`rness/policies/` contient les règles strictes de l'agent. Pas de la personnalité — de la loi. Quatre politiques sont fournies par défaut :

- **`allowlists.md`** — les règles de portée. Trois listes :
  1. *Préfixes de lecture de fichiers :* les chemins absolus que l'agent peut lire hors du projet (par défaut : `~/enough/`).
  2. *Préfixes de lecture-écriture de fichiers :* les chemins où il peut aussi écrire hors du projet. Cette liste est fournie **vide** : d'origine, l'agent n'écrit qu'à l'intérieur de votre projet, et ça reste ainsi jusqu'à ce que vous ajoutiez délibérément un chemin.
  3. *Domaines internet :* les hôtes récupérés directement (les défauts incluent `gutenberg.org`, `en.wikipedia.org`, `en.wikisource.org`, `archive.org`, `standardebooks.org`, et l'hôte de téléchargement de Kiwix). Un domaine qui n'est pas sur la liste n'est pas bloqué — la récupération est plutôt routée à travers un proxy Tor local, pour qu'une recherche ponctuelle ne laisse pas votre adresse dans les journaux d'un serveur. Un interrupteur du broker peut désactiver ce repli, faisant échouer purement et simplement les récupérations hors liste.
- **`context-management.md`** — comment l'agent détecte une fenêtre de contexte qui se remplit et se remet à zéro en douceur sans perdre son état (section 7.3).
- **`requests.md`** — quand et comment l'agent suit le travail de longue durée sous forme de fichiers de requête (section 7.3).
- **`profile-maintenance.md`** — ce qui a sa place dans le profil du projet et ce qui ne l'a pas (section 7.1).

Les politiques sont liées par symlink depuis les défauts comme tout le reste, donc vous pouvez resserrer la liste blanche globalement ou la personnaliser pour un projet qui a besoin d'une portée plus large (ou plus stricte). Modifier `allowlists.md` est en pratique la personnalisation la plus courante de toutes : ajoutez les sites de documentation en qui vous avez confiance, ajoutez un dossier partagé dans lequel l'agent devrait pouvoir écrire, et continuez votre journée.

---

## 5. Mode lecture/édition

Cliquez sur n'importe quel fichier dans l'arborescence et il s'ouvre dans le mode lecture/édition unifié : un mode à deux *faces* — une **face lecture** (l'œil) pour relire, une **face édition** (le crayon) pour changer le texte.

### 5.1 Plein contre mini, et basculer entre tout

Lecture/édition existe en deux tailles. **Mini** est un panneau latéral à côté de la discussion : gardez un document de référence sous le coude pendant que vous conversez. (Le mini panneau omet délibérément la barre d'outils de révision — il est fait pour la lecture et les modifications rapides, pas le balisage.) **Plein** prend tout le cadre, pour les documents longs et l'édition sérieuse.

Changez de taille avec le bouton mini↔plein dans l'habillage du panneau. Changez de face avec le bouton de bascule de face juste à côté. ⌘S enregistre dans la face édition. Quand ce que vous regardez est le jumeau d'un document converti, l'habillage nomme aussi l'original et porte un bouton **exporter** pour réécrire vos changements dedans (section 6.5). Et tout est protégé contre la perte : si vous avez des modifications non enregistrées, enough vous prévient avant de laisser quoi que ce soit les abandonner — naviguer vers un autre fichier, fermer le mode, rebondir vers un autre document. Vous ne perdrez pas une heure de travail à cause d'un clic malheureux.

Pendant qu'un document est ouvert, trois compteurs apparaissent dans la barre supérieure et suivent votre frappe : **¶** paragraphes, **W** mots, **C** caractères. (La vue liste de l'écran d'accueil vous montre les trois mêmes totaux pour tout un projet — section 2.1.)

Comme chaque mode plein cadre, lecture/édition affiche son icône dans la zone d'indicateurs en haut à droite, avec un petit ruban croix-rouge accroché pour fermer (section 12).

### 5.2 Surlignage

Dans la face lecture de n'importe quel document markdown, sélectionnez du texte et peignez-le d'une des quatre couleurs — **jaune, vert, bleu, rose** — depuis la barre d'outils ou le popup qui apparaît au-dessus d'une sélection. La même barre d'outils propose une mise en forme légère : gras, italique, souligné (⌘B / ⌘I / ⌘U).

Les surlignages sont durables, et ils vivent hors bande : chaque document reçoit un fichier annexe caché (`.<nomdufichier>.highlights.json`) plutôt que du balisage épissé dans votre texte, si bien que le document lui-même reste propre. Une bande colorée dans la marge marque chaque ligne surlignée. Les surlignages persistent d'une session à l'autre, et les couleurs superposées s'empilent.

Voici la partie qui change votre façon de travailler : l'agent peut les voir. Son outil `read_highlights` liste chaque surlignage d'un document par couleur, et `navigate_to_highlight` fait sauter la vue vers l'un d'eux. Ça transforme le surlignage en canal de communication. Peignez en jaune les quatre paragraphes que vous voulez réécrits et en vert les deux que vous adorez, puis dites « réécris les parties jaunes ; garde le ton des vertes ». Quand vous mentionnez une couleur, l'agent comprend que vous parlez de vos surlignages.

### 5.3 Types de fichiers pris en charge

- **Markdown (`.md`)** s'affiche mis en forme dans la face lecture et comme source dans la face édition. Markdown est la langue maternelle d'enough — presque tout ce que le système lui-même écrit est du markdown.
- **Le texte brut**, et tout ce qui y ressemble, s'ouvre en lecture/édition comme du texte.
- Les fichiers **`.girraph`** s'ouvrent en mode girraph à la place (section 17).
- Les fichiers **`.merirmaid`** s'ouvrent en mode merirmaid à la place (section 18).
- Les **articles Wikipédia enregistrés** (`article.html` à l'intérieur d'un dossier `wiki/`) s'ouvrent dans le lecteur wikisink en fidélité complète (section 10.2).
- **Documents Word, PDF, ebooks, présentations, classeurs** s'ouvrent comme un **jumeau** markdown modifiable — une ligne dans l'arborescence, un clic, et un bouton **exporter** dans l'habillage pour réécrire vos changements en retour. C'est la section 6, et c'est toute l'histoire.
- Les **images** (`.png`, `.jpg`, `.gif`, `.webp`, `.bmp`, `.svg`) s'ouvrent dans une visionneuse simple (section 6.9). Les images *à l'intérieur* d'un document s'affichent dans la face lecture comme n'importe quelle autre image en markdown.

enough reste un système de texte, et le restera : il affiche du markdown, pas de la mise en page. Ce qu'il fait avec tout le reste, c'est le convertir — assez sans perte pour qu'on puisse y travailler, assez honnêtement pour vous dire ce qui n'a pas survécu.

---

## 6. Travailler avec des PDF, documents Word, et autres fichiers

enough n'affiche pas un PDF, ne met pas en page un document Word, ne dessine pas un tableur, et ne prétend pas le faire. Ce qu'il fait à la place est plus discret et, pour le genre de travail que vous faites ici, plus utile : il convertit le document en markdown que vous pouvez réellement lire, modifier, surligner, et remettre à votre agent — et il garde ce markdown lié à l'original, pour que vos changements puissent y retourner.

Rien de tout ça n'est un mode séparé ni une application séparée. Vous cliquez sur le fichier. Il s'ouvre.

### 6.1 Le jumeau

Ouvrez `memo.docx` et enough écrit `memo.docx.md` à côté. Ce second fichier est le **jumeau** : une simple copie markdown du document, posée dans votre dossier de projet, à vous de la modifier comme n'importe quoi d'autre. La créer ne modifie jamais l'original.

Dans l'arborescence de fichiers, vous voyez toujours une seule ligne — `memo.docx`. Le jumeau, le dossier d'images extraites du document (`memo.docx.assets/`), et un petit fichier caché enregistrant ce qui a été converti depuis quoi sont tous repliés dans cette ligne unique, si bien que votre projet continue de ressembler à ce qu'il est dans Finder. Cliquez sur la ligne et le jumeau s'ouvre en mode lecture/édition (section 5) avec tout ce que ce mode offre : deux faces, ⌘S, la protection contre la perte — et, une fois en plein cadre, les surlignages.

Deux conséquences à connaître. Le nommage ne peut pas entrer en collision : un `memo.md` que vous avez écrit vous-même est un fichier différent de `memo.docx.md`, et enough ne les confond jamais. Et si vous supprimez `memo.docx` dans Finder, rien ne casse — le jumeau devient discrètement un fichier markdown ordinaire dans votre arborescence, ce qu'il a toujours été de toute façon.

Votre agent voit la même chose que vous. Demandez-lui de lire `report.pdf` et il obtient le jumeau, en en convertissant un d'abord s'il n'y en a pas encore ; demandez-lui de changer quelque chose et il modifie le jumeau, exactement là où vont vos propres modifications.

### 6.2 Ce qu'enough peut ouvrir de cette façon

Cette liste vient de l'application elle-même plutôt que d'un texte que quelqu'un doit penser à mettre à jour — si vous lisez ceci en dehors d'enough, ouvrez le centre d'aide dans l'application (section 9) pour la voir remplie :

{{convert-formats}}

### 6.3 Le badge dans l'arborescence

Chaque document convertible porte un petit badge au bord droit de sa ligne, et ce badge a exactement un travail : vous dire si les deux moitiés sont toujours d'accord.

- **Discret** — converti, et les deux côtés correspondent. Rien à faire.
- **Allumé, dans votre couleur** — vous avez modifié le jumeau. Ces changements sont dans le markdown et pas encore dans l'original ; exportez quand vous êtes prêt (section 6.5).
- **Allumé, dans la couleur de l'agent** — l'original a changé hors d'enough depuis sa conversion. Quelqu'un l'a modifié dans Word ; une nouvelle copie a atterri par-dessus ; il est arrivé depuis un disque partagé.
- **Allumé, dans la couleur d'erreur** — les deux à la fois. C'est le seul cas où enough vous pose la question, et il la pose (section 6.7).
- **Creux** — convertible, pas encore converti. Cliquez dessus et il se convertit.
- **Creux, et cliquer explique un extra** — un PDF, une présentation, ou un classeur sur une installation qui ne sait pas encore les lire (section 6.8).

Survolez le badge pour la même chose en une phrase. Cliquer sur le badge fait exactement ce que fait cliquer sur le nom du fichier.

### 6.4 La première fois que vous en ouvrez un

La première fois que vous ouvrez chaque *type* de document, une courte modale explique ce qui va se passer — ce qu'est un jumeau, où il va, que l'original reste en place. Un seul bouton OK. C'est une fois par type, pas une fois par fichier : votre deuxième document Word s'ouvre simplement.

La conversion d'un document bureautique est rapide, bien en dessous d'une seconde pour tout ce qui est typique. Vous verrez un petit toast dans le coin pendant qu'elle tourne, avec un bouton **annuler** sur les plus lentes. Les PDF prennent plus de temps et ont droit à une barre de progression honnête (section 6.8).

### 6.5 Exporter vos changements en retour

Un jumeau ouvert porte un bouton **exporter** dans son habillage. Une modale, trois décisions :

**Quel format.** Le format propre à l'original est présélectionné, et le reste des cibles d'export est là aussi — un document Word peut sortir en PDF, en EPUB, ou en page HTML autonome. Tout ce que le format ne peut pas faire s'affiche grisé avec la raison, jamais silencieusement absent.

**Une copie, ou l'original.** Le défaut est une **copie datée** écrite à côté de l'original — `memo-2026-08-19-1042.docx` — et le nom de fichier exact est prévisualisé dans la modale avant que vous ne validiez. Rien n'est en jeu : vous obtenez un nouveau fichier, l'ancien n'est pas touché. La seconde option écrase l'original sur place, et elle n'est proposée que quand le format vers lequel vous exportez est celui de l'original. Choisissez-la et enough vous propose une **annulation** ensuite : garder le nouveau fichier, ou remettre les anciens octets, octet pour octet.

**Si vous voulez le garder synchronisé** à partir de maintenant — section 6.6.

Un mot sur ce qui survit au voyage. Écraser un `.docx` ou un `.odt` utilise l'original comme référence de style, donc la taille de page, les polices, et les éventuels en-têtes et pieds de page courants reviennent avec votre texte — des choses que markdown n'a aucun moyen d'exprimer et qui seraient sinon perdues. Ce que markdown ne peut vraiment pas transporter ne revient pas : suivi des modifications et commentaires (acceptés puis abandonnés à l'entrée), zones de texte, champs, dimensionnement précis des images. Cette asymétrie explique pourquoi la copie datée est le défaut, et pourquoi enough ne réécrit jamais un original de sa propre initiative.

### 6.6 Garder l'original synchronisé

Cochez **garder l'original synchronisé** dans la modale d'export et chaque enregistrement du jumeau réécrit discrètement l'original aussi. Modifiez dans enough, et le `.docx` sur votre disque est à jour dès qu'un collègue le demande. C'est un réglage par fichier, il s'applique dès l'instant où vous le cochez, et une petite confirmation apparaît chaque fois qu'un enregistrement se propage.

C'est proposé pour les formats qui peuvent être réécrits — Word, OpenDocument, Rich Text, EPUB ; la colonne « garder synchronisé » de la section 6.2 fait autorité. Les PDF ne peuvent pas participer, et la raison mérite d'être dite clairement : enough peut *écrire* un PDF à partir de markdown, mais il recompose le document depuis zéro. Un PDF synchronisé remplacerait votre original soigneusement mis en page par une simple recomposition de ses mots, à chaque enregistrement. Ce n'est pas une synchronisation, c'est une démolition, donc ce n'est pas proposé.

### 6.7 Quand les deux côtés ont changé

L'original peut évoluer sans vous. Vous modifiez le jumeau ici ; quelqu'un modifie le `.docx` dans Word ; il y a maintenant deux versions de la vérité.

enough le remarque. Il compare l'original à ce qu'il avait enregistré au moment de la conversion, à chaque instant qui compte — quand l'arborescence est dessinée, quand vous ouvrez le document, quand vous enregistrez, quand vous exportez — et un fichier simplement *touché* (copié, sauvegardé, ouvert puis fermé) ne compte pas : la vérification lit le contenu, pas seulement les horodatages.

Quand les deux côtés ont vraiment changé, vous obtenez une modale avec trois choix en mots simples :

- **Garder mon jumeau.** Rien n'est écrit. Le badge revient à « vous l'avez modifié » et vous déciderez plus tard.
- **Exporter par-dessus l'original.** Votre markdown l'emporte ; l'original est réécrit, avec une annulation proposée comme d'habitude.
- **Reconvertir depuis l'original.** L'original l'emporte ; un nouveau jumeau est écrit — et votre ancien jumeau est mis de côté comme fichier d'annulation plutôt que supprimé.

Aucun choix dans cette modale ne détruit quelque chose que vous ne pouvez pas récupérer. C'est la règle de conception sur laquelle toute la fonctionnalité est construite.

### 6.8 Lire des PDF, présentations, et classeurs : l'extra PDF

Lire un PDF est un problème plus dur que lire un fichier Word. Un `.docx` sait encore ce qu'est un titre ; un PDF sait seulement où l'encre est allée, et en extraire un tableau, une mise en page à deux colonnes, ou un scan demande de vrais modèles de document. Ces modèles sont volumineux, donc ils ne sont pas dans l'installation de base — ils sont à un clic de distance à la place : **⚙ fenêtre UI → extras → installer l'extra PDF**.

Ce que ça coûte, honnêtement :

- environ **250 Mo à télécharger**, et environ **1 Go sur le disque** une fois installé ;
- plus environ **0,7 Go de poids de modèle**, récupérés une fois et gardés dans `~/enough/weights/docling/` ;
- quelques minutes, en majorité du téléchargement. L'installeur diffuse son journal dans la fenêtre pour que vous puissiez regarder, et les moteurs s'activent en direct — aucun redémarrage.

Ce que vous obtenez : les **PDF**, scans compris (le texte est lu dans les pixels par OCR) ; les **présentations PowerPoint**, dont les diapositives deviennent des sections titrées ; et les **classeurs Excel**, dont les feuilles deviennent des tableaux markdown.

La vitesse, mesurée plutôt que devinée, sur silicium Apple : environ **0,9 seconde par page** pour un PDF numérique, plus un chargement de modèle ponctuel d'environ **10 secondes** par conversion. Donc un PDF d'une page prend environ dix secondes, un livre de cent pages environ une minute et demie, et une présentation ou un classeur quelques secondes. Les conversions longues affichent une progression et peuvent être annulées ; annuler ne laisse rien derrière soi — pas de jumeau à moitié écrit, pas de dossiers égarés.

Deux choses vous épargneront un moment de perplexité plus tard. D'abord : **écrire des PDF n'a besoin de rien de tout ça.** N'importe quel jumeau exporte vers PDF sur toute installation, extra ou pas, parce que le compositeur qui s'en charge est fourni avec enough. L'extra sert à *lire*. Ensuite : si le message « nécessite un extra » apparaît sur une machine où vous êtes sûr de l'avoir installé, relisez quelle phrase exacte vous avez reçue — les paquets et les poids de modèle sont deux téléchargements séparés, et une connexion coupée en cours de récupération peut vous laisser avec le premier mais pas le second. Relancer l'installation termine le travail et ne retélécharge rien que vous avez déjà.

Les mises à jour gardent l'extra. `update-enough.command` (et `/update-enough`) se souviennent de ce que vous avez installé et le redemandent à chaque synchronisation, donc une mise à jour de routine ne vous retire jamais discrètement la lecture de PDF.

### 6.9 Images, et regarder l'original

Cliquez sur une image et elle s'ouvre dans une visionneuse simple : ajustée à la largeur par défaut, cliquez pour passer à la taille réelle et faire défiler autour, un damier derrière tout ce qui est transparent, et le nom, les dimensions en pixels, et la taille du fichier dans l'en-tête. C'est en lecture seule. enough n'est pas un éditeur d'image et n'a aucune ambition dans ce domaine.

Les images *à l'intérieur* d'un document, c'est une autre affaire, et elles passent bien : la photo de votre fichier Word est extraite dans `memo.docx.assets/` et s'affiche dans la face lecture du jumeau exactement comme n'importe quelle autre image markdown.

Et quand le jumeau ne suffit pas, l'habillage d'un PDF porte **voir l'original** : ça ouvre le vrai PDF dans le panneau, pour que vous puissiez vérifier le jumeau par rapport à la vraie page. Fermez-le et vous êtes de retour dans le jumeau, là où vous l'aviez laissé.

### 6.10 Ce que la conversion vous coûte, en deux phrases

Deux limites méritent d'être nommées à voix haute plutôt que de vous laisser les découvrir. Les feuilles d'un classeur arrivent comme des tableaux mis bout à bout **sans titres de nom de feuille** — le lecteur ne les émet pas, et enough préfère laisser un vide plutôt qu'inventer une étiquette. Et une image extraite d'un PDF reçoit le texte alternatif « Image », à chaque fois : il n'y a pas de légende dans le fichier pour lui en donner une meilleure.

Au-delà de ça, la promesse permanente : **vos originaux ne sont jamais modifiés sauf si vous le demandez.** Convertir ne fait jamais qu'écrire de nouveaux fichiers à côté d'eux. Exporter-écraser est le seul chemin qui touche un original, ça demande un clic délibéré, et ça vous laisse une annulation.

---

## 7. Le dossier de projet et `rness/`

Un projet est un dossier. N'importe quel dossier. enough y ajoute exactement une chose : `rness/`, le cerveau externalisé de l'agent pour ce projet. Tout ce que l'agent est, sait, et retient ici vit dans ce dossier sous forme de fichiers ordinaires. Vous pouvez tout lire, tout modifier, et le mettre sous git si c'est votre habitude.

L'agencement :

```
your-project/
  rness/
    AGENT.md            who the agent is here          (4.1)
    MOTIVATION.md       why it works                   (4.1)
    active-paradigm     which paradigm is in force     (14)
    paradigms/          available reasoning frameworks (14)
    skills/             available skills               (16)
    roles/              available personas             (15)
    policies/           the hard rules                 (4.2)
    knowledge/          project memory                 (7.1)
    io/                 input/output workspace          (7.2)
    requests/           long-running work tracking      (7.3)
  ...your actual files...
```

Les entrées liées par symlink (en italique dans l'arborescence) suivent les défauts globaux ; personnalisez n'importe laquelle d'entre elles pour en forker une copie locale (section 3.1). Les fichiers que vous déposez dans le projet par n'importe quel moyen — Finder, un autre éditeur, l'agent — sont également visibles pour tout le monde au tour suivant.

Un document converti (section 6) ajoute lui aussi des fichiers ici, toujours à côté de l'original et toujours nommés d'après lui : `memo.docx` obtient un jumeau à `memo.docx.md`, ses images dans `memo.docx.assets/`, et un `.memo.docx.convert.json` caché qui enregistre ce qui a été converti depuis quoi et quand. L'arborescence replie les trois dans la ligne de l'original, mais ce sont des fichiers ordinaires sur votre disque — vous pouvez copier la paire vers une autre machine, la mettre sous git, ou supprimer le jumeau et recliquer sur l'original pour en obtenir un tout frais. Le manifeste caché est la comptabilité d'enough ; laissez-le tranquille et il reste exact. Supprimez-le et enough traite simplement le document comme jamais converti.

### 7.1 Le dossier knowledge

`rness/knowledge/` est la mémoire propre à chaque projet.

**`project-profile.md`** est le fichier le plus utile du dossier. Son contenu est injecté dans le prompt système de l'agent à chaque tour : tout ce qui est écrit ici est dans la mémoire de travail de l'agent, sans recherche nécessaire. L'agent le tient à jour au fil de votre travail — préférences observées, fichiers et personnes récurrents, conventions que vous avez adoptées, fils laissés ouverts — et vous pouvez le modifier directement. Énoncez une préférence permanente une fois dans le profil plutôt que de la répéter à chaque session. La politique profile-maintenance garde le fichier discipliné : des observations concrètes plutôt que des étiquettes vagues, de la distillation plutôt que de l'archive.

**`session-logs/`** contient un journal markdown daté des tours de chaque session, plus le journal du broker (section 8). Un historique en ajout seul. Parcourez-le, ou grep-ez-le, quand vous devez reconstituer ce qui s'est passé mardi dernier.

Au-delà de ces deux-là, le dossier est à vous. Ajoutez un sous-dossier `glossary/`, un fichier de leçons apprises, des notes de contexte — l'agent peut consulter tout ce que vous mettez ici.

### 7.2 Le dossier io

`rness/io/` est l'espace de travail de passage :

- **`input/`** — déposez des fichiers ici pour que l'agent les traite. Les pages web récupérées atterrissent aussi ici automatiquement, converties en markdown et mises en cache, si bien qu'une page récupérée une fois reste ancrée pour toujours.
- **`output/`** — là où atterrissent les artefacts générés. Passez en revue, gardez ce qui est bon, videz le reste.
- **`cloud-cache/`** — si vous utilisez l'emplacement de modèle cloud, chaque échange cloud est enregistré ici (section 13.2). Même le travail dans le cloud laisse une trace papier locale et grep-able.

### 7.3 Requêtes : comment les travaux longs survivent

Celle-ci figure rarement dans les visites express de démarrage, mais c'est le mécanisme qui rend possible le travail sur plusieurs sessions, alors ça vaut deux minutes.

Quand vous demandez quelque chose qui prendra plus d'un tour ou deux, l'agent ouvre un **fichier de requête** dans `rness/requests/` : un enregistrement markdown de l'objectif, des points de contrôle de progression, et des décisions prises en chemin. Vous n'avez pas à le demander. Reconnaître la forme d'une tâche, c'est le travail de l'agent.

Le fichier de requête compte parce que les fenêtres de contexte se remplissent. enough surveille la pression conversationnelle, et — selon la politique context-management — l'agent enregistre son état dans le fichier de requête actif avant que ça déborde. Selon votre réglage d'orchestrateur, enough se remet ensuite automatiquement à zéro (effaçant la conversation en mémoire et reprenant à neuf depuis le point de contrôle) ou fait une pause avec une bannière pour que vous remettiez à zéro quand vous êtes prêt. Dans tous les cas, c'est le système de fichiers qui est la vraie mémoire, pas la conversation : une session neuve lit le bloc Continuation du fichier de requête et reprend là où les choses en étaient.

Les requêtes terminées se déplacent vers `rness/requests/done/` — cliquez sur **marquer comme terminé** sur une requête ouverte, ou dites-le à l'agent. Le dossier done est protégé en écriture pour l'agent, et il fait aussi office de journal honnête de tout ce que vous avez réellement livré tous les deux.

---

## 8. La fenêtre broker

Le broker est l'ancre de confiance d'enough. Chaque appel d'outil que fait l'agent — chaque lecture de fichier, écriture de fichier, commande shell, et récupération web — passe par lui. La fenêtre broker 🔀 est l'endroit où vous observez et ajustez tout ça.

Onze interrupteurs, en groupes :

| Interrupteur | Ce qu'il contrôle |
|---|---|
| trace log | Si le broker écrit ou non son journal |
| local models only | Si l'emplacement cloud (OPRO-API) est même proposé dans le sélecteur de modèle |
| read_file / write_file / shell brokered | Journalisation de trace par outil, un interrupteur chacun — trois en tout (les listes blanches sont *toujours* appliquées quoi qu'il arrive) |
| fetch_url enabled | Si l'outil de récupération web de l'agent fonctionne du tout |
| Tor for off-list fetches | Domaines hors liste blanche : router via Tor (activé) ou refuser (désactivé) |
| cache & convert fetches | Convertir les pages récupérées en markdown et les mettre en cache dans `rness/io/input/` |
| wikisink tools | Si les quatre outils wiki de l'agent fonctionnent (votre propre navigation 🚰 n'est jamais soumise à contrôle) |
| wikisink live updates | Si les passes de mise à jour peuvent contacter Wikipédia du tout (désactivé = rapport depuis l'état local uniquement) |
| cacheawl tools | Si les outils de cachebox de l'agent fonctionnent (votre propre mode cacheawl n'est jamais soumis à contrôle) |

Tout est activé par défaut : les défauts font confiance à l'agent avec le projet et le gardent honnête grâce à une trace papier. Cette trace — le **journal de trace** — atterrit dans `rness/knowledge/session-logs/<date>-broker.md` : horodatage, outil, décision, arguments, résultat, pour chaque appel passé par le broker. Et quand un interrupteur ou une liste blanche bloque quelque chose, l'agent reçoit un message de refus clair disant ce qui a été bloqué et pourquoi, pour qu'il puisse vous le dire plutôt que d'échouer en silence.

Remarquez le principe de conception dans ce tableau : les interrupteurs qui contrôlent les outils de l'agent ne contrôlent jamais *votre* interface. Désactiver cacheawl tools ne vous exclut pas du mode cacheawl. Ça veut dire que l'agent ne peut pas accéder au dépôt de sa propre initiative.

---

## 9. La fenêtre UI et les docs d'aide

Le bouton UI ⚙ ouvre les préférences d'affichage et le matériel de référence. Un petit bouton **aide** se trouve en haut à droite de cette fenêtre, à côté du × : il ouvre ce manuel en lecture seule, dans l'application, comme un mode plein cadre comme les autres (section 12).

La sortie voyage désormais sur la barre de titre : **fermer le projet → accueil**, là-haut à côté du bouton aide, qui met fin à cette session et vous ramène à l'écran d'accueil (section 2.5). Elle demande avant de le faire, et elle précise ce qu'elle ne fait pas — le dossier sur le disque n'est pas touché. Dans l'application, vous auriez plus probablement recours à ⌘W ; ce bouton, c'est la même chose, et c'est le *seul* moyen si vous faites tourner enough dans un navigateur. (Il n'est pas là sur l'écran d'accueil lui-même, où il n'y a pas de projet à fermer.)

Elle contient aussi la seule chose dans enough que vous pouvez installer depuis l'intérieur d'enough : la ligne **extras** pour la **lecture de PDF** (section 6.8). La ligne dit où vous en êtes — non installé, en cours d'installation, installé, ou installé mais pas terminé — et le bouton d'installation diffuse tout son journal dans la fenêtre pendant qu'il tourne, si bien qu'un long téléchargement devient quelque chose que vous pouvez regarder plutôt que quelque chose que vous subissez. Une fois terminé, les PDF commencent à s'ouvrir ; rien n'a besoin de redémarrer.

### 9.1 Thèmes

Quatre sont fournis avec enough : **Enough Default** (violet-bleu profond et sombre), **Pastel** (papier pâle, dans l'esprit du thème « Man Page » du Terminal), **Wireframe**, et **Darknest**. Le changement est instantané, et chaque icône de l'interface redérive sa variante claire ou sombre à la volée.

Les thèmes ne sont pas codés en dur. Ils vivent dans `~/enough/config/ui.json` comme des blocs nommés de valeurs de couleur, chacun appliqué comme une propriété CSS personnalisée. Copiez un bloc existant, renommez-le, changez les couleurs, rechargez : votre thème est dans le menu déroulant. Le bloc `_doc` en tête du fichier explique chaque clé.

### 9.2 Polices

Même motif. Quatre familles fournies — SF Mono, sans-serif système, Georgia serif, Courier — et vos propres ajouts sont bienvenus dans le même `ui.json`. Pour la taille, voyez les deux molettes ci-dessous (section 9.3) — et dans un onglet de navigateur, le bon vieux zoom du navigateur (⌘+ / ⌘−) fonctionne toujours très bien par-dessus.

### 9.3 Dimensionnement — échelle de l'ui et échelle du texte

Le zoom du navigateur avait toujours été la réponse ici, jusqu'à ce que l'application de bureau arrive sans navigateur enroulé autour d'elle. Alors enough s'est développé le sien, et en a profité pour faire encore mieux : deux molettes au lieu d'une, sur la ligne sous le thème.

**l'échelle de l'ui** redimensionne *tout* — icônes, étiquettes, barre latérale, discussion, cette fenêtre même — par pas de 0,1×. **l'échelle du texte** redimensionne seulement le document devant vous : la page en lecture/édition, un article wikisink, l'aperçu de fichier, ce manuel en mode référence. Elles se multiplient, et elles ne se gênent pas : une interface à 0,9× autour d'un texte à 1,5× est une très bonne façon de lire un manuscrit, et l'inverse est une très bonne façon d'en réduire un pour qu'il ne gêne pas votre après-midi. Cliquez sur l'un ou l'autre chiffre pour ramener cette molette à 1,0× et laisser l'autre tranquille.

Les deux sont mémorisées **par dossier de projet** — le manuscrit que vous lisez depuis l'autre bout de la pièce et les notes que vous gardez sur le bureau ont chacun leur propre taille, et ni l'une ni l'autre n'entraîne l'autre avec elle. L'écran d'accueil reste à la taille normale, donc les molettes n'y apparaissent pas.

Les limites respirent avec votre écran : environ 0,5× à 2× sur les écrans d'aujourd'hui, se resserrant sur une petite fenêtre pour que l'interface garde toujours assez de place pour être elle-même, se desserrant sur des écrans très grands et très denses (le mur 8K de 2046 a droit à 3×). Quand un pas franchirait la limite, le bouton frétille, le chiffre pulse en rouge, et rien ne change — c'est tout le message d'erreur.

### 9.4 Langues

L'interface parle six langues : anglais, français, espagnol, allemand, chinois, et japonais. Le menu déroulant **langue de l'interface** sur la même ligne change tout ce que vous regardez — étiquettes, infobulles, bulles `(?)`, ce manuel — en direct, sans redémarrage. Le choix est global à la machine, voyageant dans `ui.json` comme le thème, donc l'accueil et chaque projet sont d'accord là-dessus.

Ce qu'elle ne touche délibérément *pas* : vos fichiers, votre discussion, votre agent. Parlez à l'agent dans la langue qui vous convient — les modèles locaux sont à l'aise dans ces six langues — mais enough garde son propre échafaudage (compétences, paradigmes, prompts, fichiers de projet) en anglais, parce que c'est la langue que les modèles lisent le plus fidèlement. Quelques éléments générés restent en anglais aussi — les listes tirées en direct de ce qui est installé sur *votre* machine, comme les compétences dans une bulle ou le tableau des formats de fichier. Et partout où une traduction n'a pas encore rattrapé une nouvelle étiquette anglaise, vous verrez l'anglais plutôt qu'un vide : moins joli, jamais cassé. Vous en repérez une ? C'est un bug — [enough.support](https://enough.support) l'accueille volontiers.

### 9.5 Aide-mémoires

Deux colonnes de référence, juste dans la fenêtre UI.

**Raccourcis clavier :**

| Touches | Action |
|---|---|
| esc | ferme le mode ouvert le plus au-dessus |
| ⌘ \ | affiche / masque la barre latérale |
| ⌘ K | place le curseur dans le champ de discussion |
| ⌘ Enter | envoie le message |
| shift Enter | saut de ligne au lieu d'envoyer |
| ⌘ B / I / U | gras / italique / souligné sur la sélection (face lecture) |
| ⌘ S | enregistrer (face édition) |
| ⌥ clic | menu contextuel de l'arborescence |

(Sur un clavier non-Mac : Ctrl pour ⌘, Alt pour ⌥.)

Ce sont les raccourcis que l'interface elle-même gère, donc ils fonctionnent aussi bien dans l'application que dans un onglet de navigateur. L'application en ajoute deux siens, depuis la barre de menus : **⌘W** ferme le projet et vous ramène à l'écran d'accueil (section 2.5) — il ne ferme *plus* la fenêtre — et **⌘Q** quitte, comme il l'a toujours fait.

**L'aide-mémoire markdown :** titres, listes, liens, code, citations — toute la référence rapide, pour quiconque est encore en train de devenir couramment bilingue en markdown. Ce qui vaut la peine, puisqu'enough le parle nativement partout.

### 9.6 Aide intégrée (IHH)

Les bulles `(?)` disséminées dans l'interface sont le système d'aide intégré : une bulle par concept — compétences, rôles, le sélecteur de paradigme, rness, io, knowledge, cacheawl, wikisink, le système de modes, les documents convertis, et ainsi de suite — chacune avec un **what**, un **how**, et une liste **ideas**. Les bulles compétences, rôles, et paradigmes listent ce qui est réellement installé dans *votre* projet, et la bulle document-converti tire son tableau de types de fichiers du registre de formats propre à l'application — tout généré en direct, si bien que l'aide ne dérive jamais de la réalité. (Le même tableau apparaît à la section 6.2 de ce manuel, depuis la même source.)

Les bulles sont contrôlées par dossier de projet via la case à cocher « bulles d'aide (?) » dans la fenêtre UI. Activée par défaut pour un nouveau dossier, et le réglage colle par dossier — donc votre projet chevronné du quotidien peut se faire discret pendant qu'une expérience toute fraîche garde ses petites roues.

Même l'aide est personnalisable. Le contenu vit dans un seul fichier markdown (`enough/static/help-docs.md`) ; le modifier modifie les bulles.

---

## 10. Wikisink

Wikisink (🚰) met une copie hors ligne de Wikipédia anglais sur votre machine : consultable dans l'application, cherchable en texte intégral, lisible par l'agent, annotable, et rafraîchissable à la demande avec un rapport de changements. Une fois configuré, il n'a besoin d'aucun internet du tout.

### 10.1 Configuration

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

Une fois installé, 🚰 ouvre le lecteur : précédent et suivant, des suggestions de titre en direct dans le champ de recherche (Entrée lance une recherche en texte intégral sur toute l'archive), un dé à article aléatoire 🎲, et un badge de source qui vous dit si vous lisez l'instantané de l'archive (`ZIM <date>`), une copie plus fraîche issue d'une passe de mise à jour (`en direct <date>`), ou une copie préservée (`préservé`). Les liens internes restent dans l'application ; les liens externes s'ouvrent dans votre navigateur. La pastille de discussion en bas remet l'article actuel — ou votre passage sélectionné — directement à l'agent.

**La pastille de nouvel instantané.** Kiwix reconstruit ces archives périodiquement, et vous ne devriez pas avoir à aller le chercher. Quand une version plus récente de *votre* variante existe, une petite pastille apparaît dans la barre d'outils du lecteur — `nouvel instantané : <date> · <taille>`. Cliquez dessus, confirmez la taille, et la mise à niveau s'exécute sur place : même dossier de stockage, téléchargée d'abord et substituée seulement une fois terminée, l'ancien fichier supprimé après coup et pas avant. Vos commentaires, enregistrements, et dérogations 🛡 traversent intacts, parce qu'aucun d'eux ne vit à l'intérieur de l'archive. La pastille devient l'indicateur de progression pendant le téléchargement, puis disparaît. enough vérifie ça au plus une fois par jour, jamais pendant que le lecteur affiche quelque chose, et reste silencieux quand vous êtes hors ligne — ce qui est l'état normal d'une fonctionnalité Wikipédia hors ligne. La même mise à niveau est disponible par le chemin long, dans la liste des installations ⚙, et les passes wikisink de l'agent la signalent aussi (section 10.3) — mais appuyer sur le bouton reste toujours votre décision.

### 10.2 Enregistrer et verrouiller des articles

**Enregistrer.** Le bouton enregistrer propose deux destinations : le dossier `wiki/` de ce projet, ou le cachebox wiki global à la machine (`~/enough/cacheawl/wiki/`) partagé par tous les projets. Dans les deux cas, un enregistrement est un dossier — `article.html`, l'article octet pour octet tel que l'archive l'avait, plus `_manifest.md` portant le titre, l'url source, la date de récupération, et la ligne de licence CC BY-SA. Chaque article enregistré est autodescriptif, ce qui veut dire que si son texte finit un jour dans quelque chose que vous publiez, l'attribution dont vous avez besoin est déjà posée juste à côté. Cliquez sur un `article.html` enregistré dans l'arborescence et il s'ouvre dans le lecteur en fidélité complète — infobox, tableaux, tout — même quand aucune archive n'est accessible. Pour désenregistrer, survolez le dossier enregistré dans l'arborescence et cliquez sur le 🗑 qui apparaît.

Enregistrer, c'est pour *vous* : des copies hors-ligne-de-l'hors-ligne, l'attribution pour publication. L'agent n'a pas besoin des enregistrements — ses outils lisent n'importe quel article de l'archive en texte propre à la demande.

**Commentaires.** Sélectionnez du texte et appuyez sur 💬, ou utilisez le 💬 de la barre d'outils pour une note au niveau du paragraphe. Les fils vivent dans le panneau 🗨 : répondre, résoudre, rouvrir, sauter. Les commentaires s'attachent à l'*article*, pas à un fichier, et ils survivent aux mises à jour d'article en se dégradant en douceur. Le texte encore présent reste **ancré**. Le texte retiré par une édition est **repositionné** sur son paragraphe. Un paragraphe purement supprimé laisse le commentaire **orphelin** dans le panneau — étiqueté, mais jamais supprimé automatiquement.

**Verrouillage (dérogations de suppression).** Il arrive que Wikipédia en direct supprime un article dont vous dépendiez ; le cas classique est un sujet de niche coupé pour « notoriété » plutôt que pour sa qualité. Le bouton 🛡 préserve votre copie locale pour toujours — servie dès lors avec un badge `préservé`, exclue des futurs rafraîchissements, toujours cherchable. Les rapports de passe de mise à jour notent en fait les suppressions détectées (les justifications à la « notoriété » sont notées suspectes ; celles pour violation de droit d'auteur sont notées bénignes), pour que vous sachiez quelles suppressions méritent un coup d'œil. Et déroger reste délibérément votre décision à vous seul : l'agent peut recommander 🛡, mais il ne peut jamais l'appuyer.

### 10.3 La mise à jour wikisink, avec rapport de changements

« Wikisink » est aussi un verbe. Chaque article que vous avez enregistré ou commenté est *surveillé*, et demander à l'agent de « lancer un wikisink » (ou le laisser invoquer son outil `wikisink`) vérifie l'ensemble surveillé par rapport à Wikipédia en direct et fait un rapport. Une passe :

1. rafraîchit les articles surveillés qui ont changé dans une surcouche locale (leur badge bascule vers `en direct`) ;
2. signale les **pics d'édition** — des articles surveillés soudainement édités des dizaines de fois par jour, plus des candidats à la poussée à l'échelle de tout Wikipédia ;
3. compare le **classement quotidien des 1000 articles les plus vus** à la dernière passe : ceux qui montent, ceux qui descendent, les nouvelles entrées, les sorties, et les tendances de vues pour vos articles surveillés ;
4. vérifie les **suppressions** d'articles surveillés ou récemment vus, notées pour leur degré de suspicion (section 10.2) ;
5. note quand un **nouvel instantané de base** est disponible. Remplacer l'archive de base de plusieurs Go reste toujours votre décision — appuyez sur la pastille dans la barre d'outils du lecteur (section 10.1) ou utilisez la liste des installations ⚙. Il n'existe aucun outil agent qui la substitue.

Le rapport arrive dans la discussion en markdown ; la version complète sans plafond est gardée sous le dossier d'état de wikisink. Les passes sont polies envers Wikipédia — groupées par lots, User-Agent honnête — et reprenables si interrompues, et une passe `report-only` saute l'étape de rafraîchissement. Deux interrupteurs du broker gouvernent tout ça : l'un contrôle entièrement les outils wiki de l'agent, l'autre peut forcer les passes entièrement hors ligne.

---

## 11. Cacheawl

Cacheawl est le dépôt de texte global à la machine : l'endroit pour les choses que vous voulez garder pour toujours et atteindre depuis chaque projet. Il vit dans `~/enough/cacheawl/`, caché de l'arborescence de chaque projet, partagé entre toutes vos instances d'enough. (Si vous faisiez tourner une version antérieure d'enough, votre ancienne bibliothèque `infoworld/` a été dissoute dans cacheawl au premier lancement de la 0.1.6 — `personal/`, `public/`, et `wiki/` sont devenus vos trois premiers cacheboxes. Rien n'a été perdu.)

### 11.1 Les cacheboxes et leurs cartes merirmaid

Un **cachebox** est un dossier de premier niveau dans le dépôt, et il existe en deux variantes. Les **box simples** contiennent du texte gardé pour toujours que vous organisez vous-même : une box `personal` de notes de référence, une box `press` de textes publiés, n'importe quelle structure qui vous sert. Les **répliques mises en cache** sont des box *ingérées* depuis une source — un dossier local, un site web, ou un ensemble d'articles Wikipédia — qui se souviennent d'où elles viennent.

Chaque box porte une **carte merirmaid** : `_cachebox.merirmaid`, un diagramme en direct de la structure de la box, régénéré chaque fois que le contenu change. Double-cliquez dessus pour voir la forme d'une box d'un coup d'œil. La carte est un *mirror*, en lecture seule par conception, parce qu'elle reflète la réalité — pour changer la carte, changez la box. Une passe de réconciliation peu coûteuse garde les mirrors honnêtes même quand vous déposez des fichiers depuis Finder dans le dos d'enough.

Ouvrez le **mode cacheawl** depuis la barre supérieure pour une vue à deux volets, projet d'un côté, dépôt de l'autre. Glissez un fichier d'un côté à l'autre pour le copier. Shift-glissez pour le déplacer. Shift-cliquez pour un menu contextuel, et double-cliquez pour ouvrir n'importe quel fichier dans son mode naturel — girraph, merirmaid, lecture/édition, ou le lecteur wiki — directement depuis le dépôt.

### 11.2 Le cachebox et la capture de documents locaux ou web

La **barre d'ingestion** en mode cacheawl (ou une simple demande en conversation) capture du matériel extérieur dans une box :

- **Un chemin local** — réplique un dossier de notes ou de documents dans le dépôt.
- **Un site web** — explore un site de documentation ou de référence jusqu'à une profondeur choisie (plafonnée autour de 500 pages) et le garde en markdown local. Les ingestions web respectent vos interrupteurs de récupération et vos listes blanches, routage Tor compris.
- **Wikipédia** — tire les articles d'un sujet (plafonnés autour de 200) de votre archive wikisink vers du texte permanent, indépendant de tout projet.

Les ingestions tournent en arrière-plan. La box apparaît immédiatement avec un statut « en cours d'ingestion » que vous pouvez observer, et une ingestion échouée le dit plutôt que de prétendre avoir fini. Les outils de cachebox de l'agent (lister, créer, ingérer) sont soumis à l'interrupteur broker cacheawl ; votre propre usage du mode cacheawl ne l'est jamais.

Pourquoi s'en donner la peine ? Parce que les dossiers de projet sont un espace de travail et cacheawl un espace de bibliothèque. Ingérez une fois la documentation d'un framework, et chaque futur projet peut s'appuyer dessus hors ligne. Gardez vos notes de référence pérennes dans une box, et chaque agent à qui vous parlerez jamais peut les atteindre. Terminez un artefact et déplacez-le dans une box, où il survit à son projet.

---

## 12. Empilement de plusieurs modes actifs

Les modes plein cadre d'enough — lecture/édition, girraph, merirmaid, wikisink, cacheawl — ne se remplacent pas les uns les autres. Ils **s'empilent**, comme des feuilles de papier. Ouvrez cacheawl, ouvrez un girraph depuis l'intérieur d'une box, ouvrez un fichier de notes par-dessus : trois modes de profondeur, et fermer chacun révèle celui en dessous exactement comme vous l'aviez laissé. Même position de défilement, même descente, mêmes modifications non enregistrées.

La barre supérieure montre un indicateur carré par mode ouvert, le plus récent à gauche. Chacun porte un petit ruban croix-rouge qui ferme ce mode précis, même un enseveli. Cliquez sur l'indicateur d'un mode enseveli pour le remonter au sommet sans déranger le reste. Esc ferme toujours le mode le plus au-dessus. Quand le dernier se ferme, vous voilà de retour à la vue de discussion — la pile vide (section 4).

Deux commodités à connaître :

- Le mini panneau lecture/édition flotte *par-dessus* un mode plein cadre, donc vous pouvez garder un document sous le coude en travaillant, disons, en mode girraph en dessous.
- Ouvrir un mode déjà quelque part dans la pile ne le duplique pas. Ça retargète et remonte celui que vous aviez déjà.

---

## 13. La fenêtre de modèle

Le badge de modèle dans la barre supérieure ouvre la fenêtre de modèle : quel cerveau vous répond, ce qui est disponible d'autre, et — si vous le choisissez — l'emplacement cloud.

### 13.1 Modèles locaux : vue d'ensemble et recommandations d'usage

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

### 13.2 Support OpenRouter (l'emplacement OPRO-API)

enough est local-d'abord, pas local-seulement. Un cinquième emplacement de modèle, **OPRO-API**, route à travers OpenRouter vers des modèles cloud. Il est désactivé par défaut, délibérément laborieux à activer, et honnête sur le compromis : vos prompts et sorties quittent la machine, en échange d'une capacité de modèle de pointe et, parfois, d'un coût plus bas que ce que le matériel et l'électricité d'un modèle local comparable exigeraient.

Pour l'activer : désactivez **local models only** dans le broker, puis cliquez sur OPRO-API dans la fenêtre de modèle. Un assistant en trois écrans vous guide — trois cases de confirmation explicites (vous avez un compte, vous comprenez la facturation, vous comprenez le compromis de confidentialité), puis votre clé API, puis une vérification de santé en direct. La clé est stockée dans le Trousseau macOS. Elle n'est jamais écrite dans aucun fichier, l'agent n'a aucun moyen de la lire, et le broker refuse les commandes shell qui ressemblent même de loin à des tentatives d'y accéder. Une fois vérifiée, OPRO-API devient sélectionnable comme n'importe quel autre modèle, et son panneau de réglages propose retester, mettre à jour la clé, supprimer la clé, et votre choix de n'importe quel id de modèle OpenRouter.

Deux choses gardent l'usage du cloud responsable :

- **Tout est mis en cache localement.** Chaque échange cloud est écrit dans `rness/io/cloud-cache/` avec les comptes de tokens et un index — une trace papier locale que votre agent local peut lire plus tard.
- **`cloud_pipeline`** laisse l'agent traiter par lots de gros travaux à travers l'emplacement cloud — jusqu'à 200 étapes, avec mise en cache par étape, résumé optionnel par étape, et une passe de compilation finale — en écrivant les résultats sur le disque plutôt qu'en inondant la conversation. Demandez « un cloud pipeline qui rédige les douze résumés de chapitre » et le gros du travail se passe hors bande, entièrement journalisé.

---

## 14. Paradigmes

Un paradigme est le cadre de raisonnement de l'agent — les règles d'engagement pour la façon dont le travail se déroule. Un seul est actif à la fois (affiché en haut de la barre latérale ; cliquez sur ● pour changer), et le texte complet du paradigme actif voyage dans le prompt système à chaque tour. L'agent voit aussi un catalogue d'une ligne des autres, pour pouvoir suggérer un changement — ou en faire un — quand votre demande serait mieux servie ailleurs. Un changement initié par l'agent n'a rien d'exotique : il écrit le nom du paradigme dans `rness/active-paradigm` et vous dit qu'il l'a fait.

### 14.1 default

Conversation libre à agent unique. Le paradigme pour la plupart du travail, et l'aiguilleur qui guette les moments où un autre paradigme conviendrait mieux. Il porte aussi les conventions permanentes — comme savoir que « les parties jaunes » veut dire vos surlignages.

### 14.2 text-planning

Pour la longue piste d'élan avant la prose : faire passer un roman, un recueil d'essais, un livre non-fictionnel, ou un manifeste de « je crois que je veux écrire quelque chose » à un plan utilisable. L'agent construit un document de plan avec vous à la racine du projet — patiemment, itérativement, sur autant de sessions qu'il faut — puis, sur demande, génère par section des *échafaudages* : des guides structurels (beats, en-têtes, rappels de voix, budgets de mots) que vous développez vous-même en prose. La règle qui définit ce paradigme : **il n'écrit jamais votre prose.** Les échafaudages ne contiennent que de la structure. Votre voix reste votre voix. (Il s'active aux côtés de la compétence `analyzer` ou `memoir-dialectic` ; les mémoires sont confiées à memoir-dialectic, construite spécifiquement pour elles.)

### 14.3 translation

Déclare la traduction hors ligne comme une capacité de premier ordre. Il se marie avec la compétence `translator` (section 16.5) : quand une demande implique de faire passer du texte d'une langue humaine à une autre, l'agent bascule ici, et si la compétence est désactivée, il vous dit ce que vous manquez — et continue de le dire jusqu'à ce que vous l'activiez. Compétence activée, vous avez un traducteur local d'environ 419 langues, sans compte, sans limite de débit, et sans dépendance réseau.

### 14.4 workflow-design

Le paradigme à propos d'enough lui-même, actif chaque fois que vous créez ou changez le flux de travail plutôt que de travailler à l'intérieur : nouvelles compétences, nouveaux rôles, nouveaux paradigmes, modifications d'AGENT.md ou de MOTIVATION.md. Ici l'agent se comporte comme un collaborateur de conception réfléchi — des questions de clarification avant de construire (périmètre ? nom ? conditions de déclenchement ?), des alternatives quand votre premier instinct pourrait être plus affûté, et un fichier de requête suivi pour chaque construction, puisque les changements de flux de travail survivent aux conversations qui les produisent. C'est le paradigme qui rend la section 3 réelle.

---

## 15. Rôles

Un rôle est un second personnage que vous pouvez convoquer dans la conversation : son propre `AGENT.md` et `MOTIVATION.md`, le même motif à deux fichiers qui définit votre agent principal, circonscrit à un caractère complémentaire — ou délibérément contradicteur. Activez les rôles par projet dans la barre latérale. Les rôles activés voyagent dans le prompt système, et vous faites appel à eux par leur nom (« que dirait open-skeptic de ce plan ? »).

### 15.1 block-breaker

Un spécialiste du blocage d'écriture, distillé à partir des réponses d'un vrai écrivain sur la façon dont il dissout le fait d'être coincé. Il diagnostique avant de prescrire — à court d'idées, à court de cran, à court de structure, et à court de permission sont quatre problèmes différents — puis fait appel à des contraintes, du brainstorming par répétitions (« dix variations, puis on taille »), des recadrages étranges, et, quand on le veut, de vraies phrases suivantes. Implacablement anti-défaitiste. Sa croyance centrale : pour quiconque écrit volontairement, le blocage se résout toujours, parce que les règles ont été inventées et que le remède peut l'être aussi.

### 15.2 open-skeptic

Un « oiseau de mauvais augure éclairable » : sincèrement enthousiaste pour l'IA là où elle est forte, professionnellement méfiant là où elle est survendue. Convoquez-le quand vous êtes sur le point de construire un flux de travail et voulez que les modes d'échec soient nommés tôt. Il résiste à l'idée de demander à l'IA de répliquer l'expérience humaine, aux chaînes d'erreurs qui s'accumulent sans relecture humaine, et à la confiance fluide qui fait le travail de l'expertise — tout en applaudissant l'IA comme moteur de collation, prothèse de connaissance, et partenaire de répétition. Il change d'avis face aux preuves : montrez-lui un flux de travail qui marche et il le dit, tout simplement.

### 15.3 Construire le vôtre

Deux exemples, un seul motif — des instructions plus une motivation, dans deux fichiers markdown. Les rôles sont le moyen le moins coûteux d'ajouter une voix qui vous manque : un canard en plastique socratique, un relecteur de conformité, un personnage lecteur pour votre public cible, un expert du domaine nourri par vos propres fichiers de connaissance. Demandez-en un dans le paradigme workflow-design et l'agent vous interviewera et écrira les deux fichiers.

---

## 16. Compétences

Une compétence est un paquet de capacité ciblée : un dossier avec un `SKILL.md` (plus des docs de référence et scripts optionnels) qui enseigne à l'agent une procédure, un vocabulaire, ou une discipline. Activez les compétences par projet dans la barre latérale. Désactivé veut dire vraiment désactivé — pas du tout dans le prompt — et les nouvelles compétences arrivent désactivées, donc rien ne change dans votre dos. Une compétence non fournie par enough est lue avant même de pouvoir être activée (section 16.6). Tout désactiver est légitime aussi : conversation pure, aucun échafaudage, parfois plus de place pour que le modèle vous surprenne.

### 16.1 analyzer

Quatre modes d'analyse dans une seule compétence.

**Summarize** produit un digest d'une page, équitable, de n'importe quel texte : ce qu'il dit, à qui il s'adresse, la motivation et les biais de l'auteur, le ton, les citations clés.

**Proofread** fait de la correction légère — coquilles, orthographe — sur des documents entiers jusqu'à des livres complets, propulsée par Harper, un correcteur grammatical local à base de règles. Il produit aussi un rapport de correction séparé de suggestions et de constats de phrases répétées, pour que les corrections silencieuses et les appels au jugement restent distinguables.

**Decide** remet votre dilemme à trois personnages archétypaux tirés d'une liste intégrée de dix, qui en débattent pour le compte-rendu. Vous obtenez une recommandation *et* la transcription, pour que vous puissiez peser le raisonnement plutôt que de faire confiance à un verdict.

**Audit** lit quelque chose que vous n'avez pas encore décidé de croire — une compétence que quelqu'un vous a envoyée, un rôle, un paradigme — et vous dit ce que c'est. D'abord une explication en langage clair de ce que la chose fait réellement et pourquoi vous en voudriez, puis une passe de sécurité : tentatives d'injection de prompt, instructions qui élargissent discrètement la portée de l'agent, signaux d'alerte épistémiques, et tout code embarqué, qui reçoit aussi un scan déterministe qui n'implique aucun modèle du tout. Le verdict est l'un de trois mots — **pass**, **flag**, **fail** — appuyé par des constats nommés, jamais un score. C'est en lecture seule : l'audit n'exécute, ne modifie, n'installe, ni n'active jamais la chose qu'il lit.

Les rapports atterrissent dans `rness/io/output/analyzer/audits/<nom-compétence>/` : un `.md` daté que vous pouvez lire comme n'importe quel autre fichier, plus un petit `verdict.json` à côté. Demandez un audit par son nom à tout moment — « vérifie ça avant que je l'active », « qu'est-ce que cette compétence fait vraiment » — et enough exécute aussi ce mode pour vous, sans qu'on le demande, la première fois que vous activez une compétence qu'il n'a pas fournie. Les deux portes écrivent le même rapport dans le même dossier. La section 16.6 raconte cette histoire.

### 16.2 anything-finder

Une équipe de recherche pour les choses qui n'apparaissent pas sur la première page. Trois visages, une seule compétence.

**find** est le visage par défaut, et il porte un plan de match pour chacun des dix types de choses difficiles à trouver, plus un onzième pour les missions qui s'enlisent. **Textes** — livres du domaine public, poèmes, documents historiques. **Vidéo** — films et séries rares, perdus, ou épuisés, avec liens de visionnage et leur légalité précisée. **Images** libres de droits pour une couverture ou un zine. **Produits** — matériel obscur, synthés, instruments, et où en acheter un réellement. **Articles** — l'article coincé derrière un paywall, retrouvé comme sa copie ouverte légitime : preprint, dépôt, archive. **Code** — dépôts sous licence permissive, bibliothèques qui n'ont jamais touché GitHub comprises. **Livres** — des lectures similaires à partir de ce que vous avez déjà adoré. **Audio** — partitions, MIDI, samples, manuels de matériel. **Assets** — polices, textures, modèles 3D, images d'archive. **Données** — jeux de données, API publiques, documents gouvernementaux, archives de journaux.

Les résultats reviennent sous forme de *fiches find* : le lien, pourquoi c'est le bon élément, et — pour tout ce qui touche au droit d'auteur — pourquoi c'est libre d'usage, avec la date de publication ou la licence explicite précisée. Demandez-lui « trouve-moi une édition du domaine public de *The Moonstone* assez propre pour être composée », « où puis-je légalement regarder la version de 1974 », « existe-t-il une bibliothèque sous licence MIT qui fait ça ». Les réponses honnêtes font partie du contrat : « ça existe mais n'est pas légalement disponible » et « trois candidats, je suis à 70 % sur le deuxième » sont de vrais résultats ici, et là où la seule route est un site de piratage, il le dira et vous orientera plutôt vers la bibliothèque, le système de prêt, ou la boutique.

**patents** est le visage antériorité. Donnez-lui une invention et il lance une recherche de nouveauté structurée à travers les brevets accordés, les demandes publiées, et la littérature non-brevet, puis rapporte ce qu'il a trouvé et ce que ça signifie pour la nouveauté et la non-évidence — avec un avertissement « ceci n'est pas un conseil juridique » qui reste dans chaque rapport, parce que c'est exactement ce que c'est. « Ça a été breveté ? » « Antériorité sur un antivol de vélo magnétique qui… » « Mon idée est-elle brevetable ? » Les bases de données qu'il n'a pas pu atteindre reviennent étiquetées *non vérifié*, jamais discrètement comme *vide*.

**venture** est le visage « est-ce que c'est un business ? », et il compose les deux autres. Un balayage de marché pour ce qui existe déjà, une vérification d'antériorité, et une passe de paysage concurrentiel sur les entreprises, les alternatives open-source, les produits adjacents, et le cimetière de ceux qui ont essayé et fermé. Ce que vous obtenez, c'est une lecture équitable — ce qui est encombré, ce qui est adjacent, ce qui est réellement ouvert, et l'angle d'attaque que les preuves soutiennent réellement — suivie du meilleur argument *pour* et du meilleur argument *contre*, chaque point ancré à un lien, et une courte liste de questions auxquelles vous seul pouvez répondre. Demandez-lui « devrais-je construire ça », « est-ce que ça existe déjà comme produit », « où est le vide de marché ici ». Il ne notera pas votre idée, n'écrira pas votre business plan, et ne vous dira pas de lever des fonds. Et il traite un champ vide comme une question, pas comme un feu vert.

La sortie va dans `rness/io/output/anything-finder/`. Tout ce qu'il récupère passe par le broker comme n'importe quel autre accès web, donc un domaine hors liste blanche est routé via Tor — et quand une source refuse de répondre, le rapport nomme l'hôte et vous dit quoi ajouter à `allowlists.md`, plutôt que de laisser un trou silencieux dans les résultats.

### 16.3 girraph-merirmaid

La compétence de discipline pour les deux primitives de diagramme d'enough (sections 17 et 18). La moitié girraph enseigne une cartographie IBIS correcte : une question par tour, pas de saut aux solutions, votre confirmation comme règle d'arrêt. La moitié merirmaid porte les règles de rédaction Mermaid, comme garder des étiquettes de nœud assez courtes pour que vous puissiez les modifier confortablement. Les modes fonctionnent sans la compétence ; avec elle, l'agent devient un partenaire de cartographie véritablement discipliné.

### 16.4 memoir-dialectic

Un collaborateur de mémoires patient, sur plusieurs sessions. Il vous interroge — une ou deux questions à la fois, jamais un déluge — et classe tout : des documents de plan numérotés dans l'ordre de la conversation, un index pour reprendre rapidement, un fichier de notes pour les vidages de cerveau désordonnés, et finalement une synthèse de plan et, seulement si vous le voulez, des brouillons. Le dossier, c'est la mémoire. Vous pouvez disparaître pendant des semaines ou des années et il reprend là où vous vous étiez arrêté. Construit pour toute la gamme, de l'histoire de vie complète à un seul jalon, avec une gestion explicite des sujets sensibles et des zones interdites, et une préservation soigneuse de votre propre façon de vous exprimer — la voix compte, surtout si un brouillon approche.

### 16.5 translator

Traduction hors ligne à travers environ 419 langues via MADLAD-400 — un téléchargement unique d'environ 3 Go qui tourne sur CPU ou Apple Silicon et ne rentre jamais téléphoner à la maison. De courtes phrases à des documents entiers, des langues majeures aux langues à faibles ressources et indigènes. Traduisez une lettre, localisez un README, vérifiez ce que veut dire un passage, faites l'aller-retour d'une phrase à travers une troisième langue comme test de préservation du sens — tout ça avec le réseau débranché. Pour certaines langues à faibles ressources, un moteur optionnel NLLB-200 offre une meilleure qualité ; il porte une licence non commerciale, donc c'est optionnel via le paradigme translation.

### 16.6 Écrire les vôtres, et faire confiance à celles des autres

Les cinq ci-dessus sont des démonstrations. Le *mécanisme* de compétence — des instructions markdown, chargées quand activées, avec une `description:` qui dit à l'agent quand s'engager — est la vraie fonctionnalité. Guides de style maison, checklists de domaine, formats de rapport récurrents, procédures de traitement de données : si vous pouvez décrire une compétence en prose, vous pouvez la remettre à votre agent comme une compétence. Construisez la vôtre avec workflow-design (section 14.4), ou forkez l'une des cinq et faites-la vôtre.

L'autre bout de cette boucle, ce sont les compétences qui arrivent d'ailleurs. Une compétence, ce sont des instructions que votre agent va suivre, ce qui veut dire qu'une compétence venue d'internet mérite exactement autant de méfiance que n'importe quel autre fichier venu d'internet. Alors enough les lit pour vous :

- **Ce qu'enough fournit d'origine est de confiance, et ça se voit comme toujours.** Les cinq ci-dessus arrivent comme des liens vers les défauts propres de l'installation. Elles s'activent instantanément. Rien ne les audite.
- **Tout le reste est désactivé tant que ça n'a pas été lu.** Déposez un dossier de compétence dans `rness/skills/` — téléchargé, envoyé par un ami, décompressé d'un `.skill` — et il reste là désactivé, marqué *unverified* dans la barre latérale. La première fois que vous l'activez, enough fait tourner le mode audit d'analyzer dessus (section 16.1) avant qu'un seul mot n'atteigne l'agent. Vous voyez ça se passer dans la ligne : *unverified* → *auditing…* → *audited*.
- ***Flagged* veut dire pas activé.** Si l'audit trouve quelque chose, la ligne dit *flagged* (ou *failed*), la compétence reste désactivée, et vous obtenez deux boutons : **read report** ouvre le rapport complet dans la vue de lecture, et **activer quand même** vous demande de confirmer puis enregistre la décision comme étant la vôtre — le constat n'est pas effacé, il est outrepassé, et la ligne affiche dès lors *trusted by you*. L'audit conseille. Vous décidez. (Si vous préférez travailler dans le fichier, modifier le `verdict.json` de cette compétence en `"verdict": "pass"` fait la même chose.)
- **Modifiez une compétence et elle est relue.** L'audit est lié aux octets exacts qu'il a lus — noms de fichiers et contenus, les deux. Changez n'importe quoi et la prochaine fois que vous activez cette compétence, elle est réauditée. Ça inclut une que vous auriez précédemment activée quand même : une dérogation décrit un ensemble particulier de fichiers à un moment particulier, et elle ne survit pas à une modification.
- **Les compétences que votre agent écrit pour vous comptent aussi comme non vérifiées.** C'est délibéré, pas un oubli. Quand workflow-design écrit un nouveau `SKILL.md` dans `rness/skills/`, l'agent audite ses propres devoirs à la première activation. C'est quasi instantané quand il n'y a rien à trouver.
- **Sans modèle en cours d'exécution, un audit ne peut pas se terminer** — et il le dit, en signalant que « the llm half of the audit couldn't run » plutôt que de laisser passer la compétence. Activez un modèle et réactivez-la, ou utilisez **activer quand même** si vous savez déjà ce qu'il y a dedans.

Les rapports vivent dans `rness/io/output/analyzer/audits/<nom-compétence>/` — le même dossier où analyzer écrit quand vous demandez un audit en conversation. Deux portes, un document, et c'est un fichier markdown ordinaire que vous pouvez ouvrir, garder, ou supprimer.

---

## 17. Le mode girraph et l'extension `.girraph`

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

Dans l'application, cliquer sur un `.girraph` ouvre le mode girraph : un arbre repliable que vous modifiez directement. Cliquez sur une étiquette pour la réécrire. Survolez une ligne pour les boutons ajouter, lier, et supprimer. Cliquez sur une puce 🦒 pour descendre dans une carte imbriquée — un fil d'ariane vous ramène — et cliquez sur une puce 📄 pour lire un document référencé sur place. En discussion, dites « girraph-moi ça » ou « cartographie ça », et l'agent modifie le même fichier à travers les mêmes opérations au niveau du nœud que vous utilisez, si bien que vous pouvez travailler la carte tous les deux à la fois. Supprimer des nœuds exige toujours votre confirmation, et les enfants ne sont jamais orphelins en silence.

Un girraph peut aussi faire pousser un **mirror merirmaid** : un clic sur le bouton merirmaid dans la barre d'outils du girraph crée un diagramme Mermaid lié, à régénération automatique, de la carte — les issues en hexagones, les positions en stades, les soutiens et objections tracés dans leurs couleurs — qui se garde à jour tout seul à mesure que le girraph change. Cartographiez en girraph, jetez un œil en merirmaid.

Trois habitudes font marcher les girraphs. Formulez les issues comme des questions (« Comment finance-t-on l'année deux ? », pas « le problème d'argent »). Attachez les arguments aux positions, pas aux issues — les raisons sont des raisons pour ou contre une *réponse*. Et séparez une branche dans son propre fichier avant qu'elle ne s'étale. Activez la compétence girraph-merirmaid et l'agent vous tiendra aux trois.

---

## 18. Le mode merirmaid et l'extension `.merirmaid`

Là où un girraph cartographie un argument, un **merirmaid** dépeint une structure. Un fichier `.merirmaid` est un diagramme [Mermaid](https://mermaid.js.org/) — organigramme, diagramme de séquence, machine à états, diagramme ER, tout ce que Mermaid dessine — avec un petit en-tête de frontmatter, rendu en direct dans le navigateur. En local, bien sûr ; pas de CDN, comme tout dans enough.

Deux modalités, déclarées dans l'en-tête :

- **wip** — un tableau blanc de travail. Cliquez sur le texte de n'importe quel nœud et modifiez l'étiquette sur place, avec un compteur de caractères en direct ; les changements structurels (ajouter une boîte, recâbler une flèche) passent par l'agent via la pastille de discussion. Demandez un diagramme de votre pipeline, de votre intrigue, de votre organisation, et l'agent écrit la source, le navigateur le dessine, et vous ajustez les mots.
- **mirror** — un reflet en lecture seule d'une structure qui vit ailleurs : le contenu d'un cachebox (section 11.1) ou un girraph (section 17). Les mirrors se régénèrent quand leur source change. Pour changer l'image, changez la chose.

Les diagrammes se relient. Un nœud peut pointer vers un autre `.merirmaid`, un `.girraph`, ou un document markdown, et cliquer dessus vous y emmène, un fil d'ariane marquant le chemin du retour — si bien qu'un ensemble de diagrammes devient un atlas navigable de votre projet. Et quand un diagramme a une erreur de syntaxe, le mode merirmaid montre l'erreur plus la source brute plutôt qu'un panneau vide. Il y a toujours quelque chose à partir de quoi corriger.

La compétence girraph-merirmaid (section 16.3) porte la discipline de rédaction pour les deux types de fichier. Une règle de base qui en vient mérite d'être répétée ici : si le premier geste honnête est de poser une question, vous voulez un girraph ; si c'est de dessiner une boîte et une flèche, vous voulez un merirmaid.

---

## 19. Où aller à partir d'ici

Le moyen le plus rapide de faire d'enough le vôtre :

1. Lancez-le dans un vrai projet — quelque chose qui vous tient vraiment à cœur.
2. Passez une session à discuter, et laissez le profil du projet commencer à s'accumuler.
3. Modifiez `MOTIVATION.md` pour dire à quoi sert réellement le projet.
4. La première fois que vous répétez une instruction, arrêtez-vous. Mettez-la plutôt dans `AGENT.md`.
5. La première fois que votre travail prend une forme que les défauts ne couvrent pas, dites « concevons un paradigme pour ça » — ou une compétence, ou un rôle — et laissez workflow-design vous guider.

Cette boucle — remarquer la friction, coder le correctif, continuer à travailler — c'est tout le jeu. Les composants intégrés vous font démarrer. Le système avec lequel vous finissez, personne ne le fournit. Vous l'écrivez.

---

*enough est © 2026 Graham Smith, distribué sous licence Apache License 2.0. Le contenu Wikipédia atteint via wikisink est en CC BY-SA. Ce document : à vous de le modifier aussi.*
