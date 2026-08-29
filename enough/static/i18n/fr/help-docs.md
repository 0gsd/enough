<!-- contenu d'aide d'enough. Une section `## <id>` par bulle (?).
     Modifiez librement : `name:`/`path:` ouvrent la section ; les corps
     `### what`, `### how`, `### ideas` peuvent contenir du HTML en ligne.
     Quatre tokens d'expansion, tous résolus côté client pour que rien
     ici ne dérive de ce qui est réellement installé :
       {{skills-list}} {{roles-list}} {{paradigms-list}}
         → l'ensemble installé en direct (voir /api/help/defaults)
       {{convert-formats}}
         → le tableau des types de fichiers convertibles, avec la
           disponibilité du moteur sur cette machine (voir
           /api/convert/formats). Ne listez jamais d'extensions de
           fichier à la main dans le texte d'aide ; utilisez le token. -->

## wikisink
name: wikisink
path: ~/enough/wikisink/

### what
votre copie locale et hors ligne (d'une tranche) de wikipédia anglais — une seule archive Kiwix ZIM lue sur place, jamais extraite, si bien que le gestionnaire de fichiers ne montre que les articles que vous enregistrez explicitement. le bouton 🚰 ouvre un lecteur façon navigateur avec recherche plein texte, liens croisés, un dé à article aléatoire, une pastille de discussion avec l'agent, des commentaires, et un unique <strong>bouton enregistrer</strong> dont le menu propose deux destinations (le <code>wiki/</code> de ce projet, ou le cachebox global <code>~/enough/cacheawl/wiki/</code> partagé entre les projets). l'agent peut chercher et lire toute l'archive via ses outils wiki.

### how
le premier clic sur 🚰 lance l'assistant de configuration : choisissez une taille (top 1 M d'articles sans images ≈ 16 Go par défaut ; anglais complet ≈ 49 Go ; options plus petites aussi), choisissez un dossier de stockage (les disques externes conviennent), confirmez, et laissez tourner le téléchargement reprenable — pause, quitter, reprendre à tout moment. vous pouvez garder <em>plusieurs installations</em> à différents endroits (par exemple l'archive complète sur un disque externe plus une petite sur le disque interne) et basculer entre elles dans la liste des installations ⚙ ; si un disque est débranché, son installation s'affiche simplement comme inaccessible jusqu'à son retour. une fois installé, demandez à l'agent de lancer un <strong>wikisink</strong> pour rafraîchir vos articles enregistrés/commentés (« surveillés ») depuis wikipédia en direct et obtenir un rapport : changements sur les articles surveillés, pics d'édition, articles qui montent ou descendent en popularité, et suppressions suspectes. le bouton 🛡 sur n'importe quel article est la <em>dérogation de suppression</em> : garder votre copie locale pour toujours, exclue des mises à jour. ⚙ ouvre le gestionnaire d'installations, y compris le remplacement de l'archive de base quand un instantané plus récent sort. inutile d'aller le chercher : quand une nouvelle version de votre variante existe, une petite pastille apparaît dans la barre d'outils du lecteur (<code>nouvel instantané : date · taille</code>) — cliquez dessus, confirmez la taille, et la même mise à niveau sur place s'exécute, téléchargeant d'abord et substituant seulement une fois terminé. la vérification a lieu au plus une fois par jour, ne bloque jamais le lecteur, et reste silencieuse quand vous êtes hors ligne.

### ideas
- enregistrez les articles dont un projet dépend dans son dossier <code>wiki/</code> — des copies à fidélité complète qui se rouvrent dans le lecteur, chacune avec un manifeste d'attribution CC BY-SA intégré.
- commentez les affirmations qui vous laissent sceptique, puis lancez un wikisink plus tard — les commentaires survivent aux mises à jour d'article (repositionnés ou orphelins, jamais perdus) et les articles commentés sont surveillés automatiquement.
- quand un rapport wikisink signale une suppression suspecte (supprimé pour « notoriété » plutôt que pour qualité — le cas classique), ouvrez l'article et appuyez sur 🛡 avant le prochain remplacement de l'archive de base.

## project-wiki
name: wiki/
path: wiki/

### what
des articles wikipédia enregistrés dans ce projet depuis le navigateur wikisink (le bouton enregistrer → « ce projet »). chaque enregistrement est un dossier : <code>article.html</code> (l'article exactement comme l'archive l'avait — cliquez dessus pour le lire dans la visionneuse wikisink, fidélité complète, infobox comprise) plus <code>_manifest.md</code> (url source, licence CC BY-SA, date de récupération, origine).

### how
créé automatiquement lors de votre premier enregistrement au niveau du projet — aucune configuration. les passes de mise à jour wikisink traitent tout ce qui est ici comme <em>surveillé</em> : rafraîchi depuis wikipédia en direct et signalé dans le rapport. réenregistrer un article écrase le dossier avec la copie la plus fraîche ; pour en retirer un, survolez son dossier dans l'arborescence un instant et cliquez sur le 🗑 qui apparaît. les copies enregistrées ne sont pas faites pour être modifiées à la main — elles se désynchroniseraient de l'archive. (l'autre choix du bouton enregistrer sauvegarde plutôt dans le cachebox global <code>~/enough/cacheawl/wiki/</code>, partagé entre tous les projets.)

### ideas
- les articles enregistrés s'ouvrent dans le lecteur même quand le disque de l'archive est débranché — ce sont vos copies hors-ligne-de-l'hors-ligne.
- l'agent lit les articles via ses outils wiki (extraction de texte propre), il peut donc s'appuyer aussi bien sur les articles enregistrés que sur ceux de l'archive.
- le texte de wikipédia est en CC BY-SA : si une partie d'un article finit dans quelque chose que vous publiez, le manifeste contient tout ce qu'il faut pour l'attribution.

## wiki-comments
name: commentaires
path: ~/enough/wikisink/comments/

### what
des commentaires façon google docs sur les articles wikipédia — surlignez du texte et appuyez sur 💬, ou utilisez le 💬 de la barre d'outils pour épingler un commentaire à un paragraphe. les fils supportent les réponses et la résolution/réouverture. les commentaires s'attachent à l'<em>article</em>, pas à un fichier enregistré, donc ils suivent l'article qu'il soit enregistré, simplement consulté, mis à jour, ou même supprimé de wikipédia en direct.

### how
sélectionnez du texte dans le lecteur wikisink → commentaire 💬. l'ancrage se dégrade en douceur quand les articles changent : correspondance exacte du texte d'abord ; si le texte cité a été retiré par une édition, le commentaire se repositionne sur son paragraphe (marqué « repositionné ») ; si le paragraphe a lui aussi disparu, il survit comme « orphelin » dans le panneau. rien n'est jamais supprimé automatiquement. commenter un article l'ajoute à l'ensemble surveillé pour les mises à jour wikisink.

### ideas
- commentez les statistiques ou affirmations susceptibles de changer — après une passe wikisink, les commentaires repositionnés sont un signal que cet endroit précis a été édité.
- interrogez l'agent sur un passage surligné via le 🤖 du popup de sélection — le passage est cité automatiquement dans la discussion.

## paradigm-active
name: paradigme
path: rness/active-paradigm

### what
le cadre de raisonnement que l'agent utilise actuellement. un seul paradigme est actif à la fois ; cliquez sur un autre pour en changer. le paradigme actif est chargé en entier dans le prompt système à chaque tour, et l'agent voit aussi un bref catalogue des autres paradigmes disponibles afin de pouvoir suggérer (ou déclencher) un changement quand le travail en tirerait profit.

### how
cliquez sur ● à côté d'un paradigme pour l'activer pour ce projet. le choix est enregistré dans <code>rness/active-paradigm</code>. les changements initiés par l'agent passent aussi par l'écriture de ce fichier, et prennent effet au tour suivant. ajoutez de nouveaux paradigmes en déposant un fichier markdown dans <code>~/enough/defaults/paradigms/</code> (ou dans le <code>rness/paradigms/</code> de votre projet pour des paradigmes locaux). un bloc de frontmatter YAML en tête — <code>name:</code> et <code>description:</code> — indique à l'agent à quoi sert le paradigme.

### ideas
- Paradigmes disponibles dans ce projet : {{paradigms-list}}
- écrivez un paradigme pour chaque mode de travail distinct (recherche vs. écriture, exploration vs. exécution) et passez de l'un à l'autre au fil de la journée.
- une description de paradigme répond essentiellement à « quand devrais-je m'en servir » — écrivez-la pour l'agent, puisque c'est le signal qu'il lit pour recommander un changement.

## requests
name: requêtes/
path: rness/requests/

### what
des conteneurs persistants de tâches et sous-tâches. chaque requête est un fichier markdown qui capture l'objectif de votre demande, le raisonnement de l'agent jusque-là, et un bloc Continuation pour que le travail puisse reprendre après une remise à zéro du contexte — c'est l'unité d'effort de longue durée dans enough. elles aident aussi à poursuivre le travail si vous atteignez une limite de fenêtre de contexte. les requêtes terminées vivent aux côtés des actives dans <code>rness/requests/done/</code>.

### how
de nouvelles requêtes apparaissent automatiquement dans <code>rness/requests/</code> au fil de votre travail avec l'agent — cliquez sur n'importe quel fichier dans l'arborescence du projet pour le voir dans le panneau de fichier. de là, vous pouvez <em>marquer comme terminé</em> (le fichier se déplace vers <code>rness/requests/done/</code>) ou <em>personnaliser</em>. pour démarrer une requête manuellement, déposez un fichier markdown dans <code>rness/requests/</code> avec un bref objectif en tête.

### ideas
- traitez une requête comme un projet de longue haleine — décomposez une intention vague en une requête et laissez l'agent l'étoffer sur plusieurs sessions.
- parcourez <code>rness/requests/done/</code> comme un journal de ce que vous avez réellement accompli — c'est l'enregistrement le plus honnête de votre travail avec cet agent.
- aux points de contrôle de remise à zéro automatique du contexte, l'agent écrit un bloc Continuation dans la requête active — lisez-le avant de reprendre si vous voulez réorienter les choses.

## skills
name: compétences
path: rness/skills/

### what
des interrupteurs par projet pour les compétences — des unités de capacité ciblée liées par symlink depuis <code>~/enough/defaults/skills/</code>. les compétences actives ajoutent du vocabulaire, des recettes, ou des comportements que l'agent ira chercher en conversation. les compétences fournies avec enough sont <em>de confiance</em> et s'activent instantanément ; tout ce qui se trouve ailleurs dans <code>rness/skills/</code> — téléchargé, offert, ou écrit pour vous par votre propre agent — est <em>non vérifié</em> tant que ça n'a pas été lu, et la première fois que vous l'activez, enough l'audite avant qu'un seul mot n'atteigne l'agent.

### how
cliquez sur ● / ○ pour activer ou désactiver une compétence pour ce projet. vous pouvez ajouter des compétences locales au projet dans <code>rness/skills/</code> — les états des compétences sont enregistrés par projet. pour installer de nouvelles compétences globalement, déposez un dossier dans <code>~/enough/defaults/skills/</code> ; elle apparaît dans tous les projets (désactivée par défaut). modifiez une compétence globale à la source et le changement se propage partout où elle est liée par symlink. une compétence non vérifiée affiche une petite marque à côté de son nom qui progresse de <em>non vérifié</em> → <em>audit en cours…</em> → <em>audité</em> ; si l'audit trouve quelque chose, la ligne affiche <em>signalé</em>, la compétence reste désactivée, et vous obtenez deux boutons — <em>lire le rapport</em> (ouvre le rapport complet) et <em>activer quand même</em> (demande confirmation, puis enregistre la décision comme étant la vôtre). les rapports atterrissent dans <code>rness/io/output/analyzer/audits/&lt;skill&gt;/</code>. modifiez ensuite les fichiers d'une compétence et elle est relue à la prochaine activation.

### ideas
- Compétences disponibles dans ce projet : {{skills-list}}
- construisez des compétences globales ou locales au projet pour capturer votre style maison ou les conventions de votre domaine.
- désactivez tout pour une « conversation pure » — parfois le modèle a plus d'espace pour des éclairs de lucidité émergents sans aucun échafaudage.
- demandez à l'agent d'<em>auditer</em> une compétence avant de l'activer (le quatrième mode d'analyzer) — le même rapport que l'audit au premier usage écrit, juste selon votre propre calendrier.

## roles
name: rôles
path: rness/roles/

### what
des agents consultants que vous pouvez convoquer en conversation, puisés dans <code>~/enough/defaults/roles/</code>. chaque rôle est un dossier contenant AGENT.md (instructions) et MOTIVATION.md (motivations) — la même paire de fichiers qui définit l'agent principal, mais circonscrite à un personnage complémentaire (ou contradicteur).

### how
cliquez sur ● / ○ pour activer un rôle pour ce projet. ajoutez de nouveaux rôles globalement en créant <code>~/enough/defaults/roles/&lt;name&gt;/</code> avec AGENT.md et MOTIVATION.md à l'intérieur ; ça marche aussi au niveau du projet, et les modifications se propagent, tout comme pour les compétences.

### ideas
- Rôles disponibles dans ce projet : {{roles-list}}
- construisez un « canard en plastique » qui pose des questions socratiques au lieu de répondre.
- utilisez les fichiers de votre base de connaissances avec le paradigme <em>workflow-design</em> pour façonner un rôle d'expert du domaine (juridique, design, rédaction).

## rness
name: rness/
path: rness/

### what
le système externalisé du projet. rness/ est l'endroit où vivent la config, les instructions, les fichiers de connaissance et les journaux d'historique de chaque projet — tout ce que l'agent utilise pour ce projet. il se trouve à la racine du projet pour que vous puissiez le modifier directement avec n'importe quel gestionnaire de fichiers ou éditeur ; l'interface d'enough affiche aussi son contenu dans la barre latérale.

### how
certains contenus sont des liens symboliques vers <code>~/enough/defaults/</code> et se mettent à jour de façon centralisée. pour diverger sur un projet, ouvrez un fichier et cliquez sur <em>personnaliser</em> — il devient une copie locale au projet. ajoutez librement de nouveaux fichiers via la conversation ou le gestionnaire de fichiers de votre système ; l'agent découvrira tout fichier ajouté localement dès son prochain tour.

### ideas
- apprenez à connaître les composants qui font tourner votre flux de travail enough et modifiez-les comme bon vous semble.
- traitez-le comme une documentation vivante — qu'aurait besoin de savoir un nouveau coéquipier, un nouvel agent, ou un nouveau rôle ?
- élaguez périodiquement les connaissances obsolètes pour que l'agent ne cite pas des décisions caduques.

## agent-md
name: AGENT.md
path: rness/AGENT.md

### what
les instructions de travail de l'agent pour ce projet. utilisé à chaque tour aux côtés de MOTIVATION.md. tout ce qui s'y trouve façonne la manière dont l'agent parle, ce qu'il fait, et ce qu'il évite.

### how
cliquez sur le fichier pour le consulter ; appuyez sur <em>personnaliser</em> pour créer une copie locale au projet et la modifier. ou ouvrez <code>rness/AGENT.md</code> dans n'importe quel éditeur — les changements enregistrés prennent effet au message suivant.

### ideas
- ajoutez des garde-fous propres au projet (par ex. « toujours revérifier l'orthographe et l'exactitude avant de finaliser une modification »).
- listez les conventions de nommage de votre projet pour que l'agent n'ait pas à deviner (ou à hallucinnover).
- codifiez le style de collaboration que vous voulez — laconique, exploratoire, déférent, direct.

## motivation-md
name: MOTIVATION.md
path: rness/MOTIVATION.md

### what
le « pourquoi » de l'agent pour ce projet — valeurs, priorités, et objectifs au-delà de la simple liste de tâches. utilisé aux côtés d'AGENT.md à chaque tour.

### how
comme pour AGENT.md — cliquez pour prévisualiser, personnalisez pour obtenir une copie locale au projet, ou modifiez le fichier directement.

### ideas
- explicitez les compromis qui comptent pour vous : l'exactitude plutôt que la vitesse, la concision plutôt que l'exhaustivité, etc.
- nommez, dans vos propres mots, l'expérience utilisateur que le projet vise.
- décrivez à quoi ressemble « terminé » — l'agent calibrera là-dessus son sens de la progression.

## paradigms
name: paradigmes/
path: rness/paradigms/

### what
l'ensemble complet des cadres de raisonnement disponibles dans ce projet. chaque paradigme est un fichier markdown avec un bloc de frontmatter YAML (<code>name</code> + <code>description</code>) et un corps décrivant comment aborder le travail — heuristiques, critères de décision, quand demander plutôt qu'agir. un seul est actif à la fois (voir la section <strong>paradigme</strong> en haut de la barre latérale pour en changer).

### how
lié par symlink depuis <code>~/enough/defaults/paradigms/</code>. modifiez-le globalement pour changer le comportement dans tous les projets ; cliquez sur <em>personnaliser</em> sur n'importe quel fichier pour le forker rien que pour ce projet. de nouveaux paradigmes peuvent être ajoutés simplement en déposant un fichier markdown dans le dossier des défauts — donnez-lui un <code>name:</code> et une <code>description:</code> en frontmatter pour que l'agent sache quand le recommander.

### ideas
- Paradigmes disponibles dans ce projet : {{paradigms-list}}
- écrivez un paradigme pour chaque mode de travail distinct (recherche vs. écriture, exploration vs. exécution) et passez de l'un à l'autre au fil de la journée.
- une description de paradigme répond essentiellement à « quand devrais-je m'en servir » — écrivez-la pour l'agent, puisque c'est le signal qu'il lit pour recommander un changement.

## policies
name: politiques/
path: rness/policies/

### what
des règles strictes que l'agent doit suivre — quels outils utiliser, quels fichiers il peut lire ou écrire, comment formater les requêtes, comment gérer la pression sur la fenêtre de contexte, et quels chemins sont sur liste blanche.

### how
lié par symlink depuis <code>~/enough/defaults/policies/</code>. modifiez-le globalement pour mettre à jour les règles de tous les projets, ou personnalisez par projet. les listes blanches en particulier sont ce qu'on ajuste le plus souvent, car les chemins locaux comme les url web doivent y être explicitement listés.

### ideas
- resserrez la liste blanche de lecture/écriture quand vous travaillez avec des secrets ou du code sensible.
- ajoutez une politique pour la gestion des scripts longs ou des processus en arrière-plan.
- définissez votre propre format de point de contrôle si le bloc Continuation par défaut ne convient pas.

## knowledge
name: connaissances/
path: rness/knowledge/

### what
des connaissances propres au projet qui n'ont pas leur place dans <code>rness/io/</code> ou <code>~/enough/infoworld/</code> : contient toujours <code>project-profile.md</code> (des notes vivantes que l'agent tient sur ce projet — vos préférences et votre style de travail tels qu'observés ici, les personnes / fichiers récurrents, les conventions adoptées) et <code>session-logs/</code> (le prompt et la réponse de chaque tour, enregistrés en markdown).

### how
<code>project-profile.md</code> est injecté dans le prompt système à chaque tour — l'agent et vous pouvez tous deux le modifier. les journaux de session sont en ajout seul. ajoutez de nouveaux sous-dossiers pour toute mémoire locale au projet que vous voulez voir consultée par l'agent.

### ideas
- tenez un sous-dossier glossaire pour le jargon propre au projet.
- laissez l'agent écrire un fichier « leçons apprises » au fil de vos itérations communes.
- archivez périodiquement les anciens journaux de session pour que les recherches de l'agent restent rapides.

## io
name: io/
path: rness/io/

### what
un espace au niveau du projet pour les fichiers que l'agent lit (<code>input/</code>) ou dans lesquels il écrit (<code>output/</code>). utile quand vous voulez que l'agent traite un fichier sans polluer la racine du projet.

### how
déposez des fichiers dans <code>rness/io/input/</code> et l'agent les verra. tout ce que l'agent génère atterrit dans <code>rness/io/output/</code> — passez en revue et déplacez ce que vous voulez garder, puis videz le reste. les documents comptent aussi : un fichier word ou un pdf déposé ici s'ouvre comme un jumeau markdown et se lit comme n'importe quel autre fichier, pour vous comme pour l'agent.

### ideas
- déposez un CSV ou une transcription dans <code>input/</code> et demandez à l'agent de résumer.
- déposez le pdf que quelqu'un vous a envoyé par mail dans <code>input/</code>, cliquez dessus, et lisez-le en markdown — l'original reste exactement tel qu'il est arrivé.
- rassemblez plusieurs brouillons dans <code>output/</code> et choisissez le meilleur (ou demandez au modèle de les évaluer les uns contre les autres).
- videz les deux périodiquement — l'agent n'a pas besoin du brouillon d'hier dans son contexte.

## infoworld
name: cacheawl
path: ~/enough/cacheawl/

### what
le dépôt de fichiers global à la machine, partagé entre tous les projets enough. (ceci remplace l'ancienne bibliothèque <code>infoworld/</code> — au premier lancement de cette version, vos dossiers <code>personal/</code>, <code>public/</code> et <code>wiki/</code> ont été déplacés ici, chacun devenant un cachebox.) un <em>cachebox</em> est un dossier de premier niveau dans le dépôt : soit du texte brut que vous voulez garder pour toujours, soit une « réplique mise en cache » ingérée depuis un chemin local, un site web, ou un ensemble d'articles wikipédia. le dépôt est caché de l'arborescence de chaque projet et géré via le mode cacheawl + les outils de cachebox de l'agent.

### how
ouvrez le mode cacheawl (le bouton cacheawl de la barre supérieure) pour une vue à deux volets : votre projet d'un côté, les cacheboxes de l'autre. glissez un fichier d'un côté à l'autre pour le copier, shift-glissez pour le déplacer ; la barre d'ingestion compose une requête pour que l'agent aille chercher un chemin/site/sujet wiki. ou demandez simplement à l'agent — il peut lister, créer, et ingérer dans les cacheboxes (soumis à l'interrupteur broker « cacheawl tools »). chaque box porte un diagramme <code>_cachebox.merirmaid</code> généré automatiquement à partir de son contenu (lecture seule — il se régénère depuis les fichiers) et des métadonnées cachées ; vous ne modifiez jamais ça directement.

### ideas
- ingérez un site de documentation sur une faible profondeur pour que l'agent puisse s'appuyer dessus entièrement hors ligne.
- gardez un cachebox <code>personal</code> de matériel de référence interrogeable depuis n'importe quel projet.
- enregistrez les articles wikipédia dont vous dépendez dans le cachebox global <code>wiki</code> — partagé partout, pas lié à un seul projet.

## mode-system
name: mode lecture / édition
path: the file viewer

### what
cliquer sur un fichier l'ouvre dans un <strong>mode lecture/édition</strong> unifié à deux faces — une face lecture (l'œil) et une face édition (le crayon). il vit soit comme un mini panneau latéral à côté de la discussion, soit déployé en plein cadre ; utilisez le bouton mini↔plein pour basculer. les modifications sont protégées contre la perte, vous ne perdrez donc pas de changements non enregistrés en naviguant ailleurs par accident. les fichiers qu'enough n'affiche pas nativement s'ouvrent quand même : un fichier word, pdf, présentation ou classeur s'ouvre comme son <em>jumeau</em> markdown (voir la bulle <em>document converti</em> sur une telle ligne), et une image s'ouvre dans une visionneuse simple avec des tailles ajustée et 1:1.

### how
cliquez une fois sur un fichier dans l'arborescence pour l'ouvrir dans le mini panneau ; déployez-le en plein cadre quand vous voulez plus de place. basculez entre les faces lecture (l'œil) et édition (le crayon) avec les boutons dédiés dans l'habillage lecture/édition. chaque mode ouvert affiche un indicateur carré en haut à droite (le plus récent à gauche) avec un petit ruban croix-rouge pour le fermer — les modes <em>s'empilent</em>, donc en fermer un révèle le mode en dessous exactement comme vous l'aviez laissé. cliquez sur un indicateur enseveli pour ramener ce mode au premier plan ; appuyez sur <code>esc</code> pour fermer le mode le plus au-dessus. le même motif indicateur + ruban couvre chaque mode plein cadre (wikisink, girraph, merirmaid, cacheawl, et le mode de référence <strong>centre d'aide</strong> en lecture seule, lancé depuis le petit bouton <strong>aide</strong> en haut à droite de la fenêtre ui).

### ideas
- gardez un fichier ouvert dans le mini panneau pendant que vous discutez — référence et conversation côte à côte.
- passez en plein cadre pour les documents longs ou pour éditer, revenez en mini quand vous avez juste besoin d'un coup d'œil.

## converted-file
name: document converti
path: the original, plus its markdown twin

### what
un document qu'enough n'affiche pas nativement — un fichier word, un pdf, une présentation, un classeur — montré comme <em>une seule</em> ligne qui s'ouvre en markdown. cliquez dessus et vous obtenez son <strong>jumeau</strong> : une copie markdown écrite à côté de l'original (<code>memo.docx</code> → <code>memo.docx.md</code>) qui se lit, se surligne et se modifie comme n'importe quel autre fichier markdown. le jumeau, les images éventuelles extraites du document (<code>memo.docx.assets/</code>) et un petit manifeste caché sont repliés dans cette ligne unique, si bien que l'arborescence reste aussi nette que votre dossier l'est dans finder. le badge au bord droit de la ligne indique où en sont les choses : discret veut dire que le jumeau correspond à l'original ; un badge en couleur avec un point veut dire soit que vous avez modifié le jumeau (et pouvez exporter ces changements en retour), soit que l'original a changé hors d'enough — et rouge veut dire les deux, le seul cas où enough vous pose la question. un badge creux veut dire « pas encore converti », ou, pour les pdf, que l'extra pdf n'est pas installé.

### how
cliquez une fois. la première fois que vous ouvrez chaque <em>type</em> de document, une courte modale explique ce qui va se passer ; après ça, ça s'ouvre simplement. modifiez le jumeau comme n'importe quel fichier, puis utilisez <strong>exporter</strong> dans l'habillage du document : par défaut, ça écrit une copie datée à côté de l'original (<code>memo-2026-08-19-1042.docx</code>), et « écraser l'original » est un bouton radio juste en dessous, avec une annulation proposée ensuite. la même modale porte <em>garder l'original synchronisé</em> — chaque enregistrement du jumeau réécrit l'original pour vous — proposé seulement pour les formats qui peuvent être réécrits. si l'original a changé sous vos pieds (modifié dans word, réexporté depuis quelque part), enough le remarque à l'ouverture ou à l'enregistrement et demande quel côté l'emporte : garder votre jumeau, exporter par-dessus l'original, ou reconvertir depuis l'original — et le jumeau qu'il remplace est mis de côté pour annulation dans tous les cas. <strong>les originaux ne sont jamais réécrits sauf si vous le demandez</strong>, et chaque écrasement laisse une annulation possible.

### ideas
- ce qu'enough peut ouvrir de cette façon, et ce qu'il peut réécrire : {{convert-formats}}
- demandez à l'agent de lire un document par son nom — <code>read_file</code> sur <code>report.pdf</code> lui donne le jumeau, en en convertissant un d'abord s'il n'y en a pas encore.
- lire des pdf, présentations powerpoint et classeurs excel nécessite l'<strong>extra pdf</strong> (⚙ fenêtre ui → extras) : environ 250 Mo à télécharger, environ 1 Go installé, plus environ 0,7 Go de modèles de document dans <code>~/enough/weights/docling/</code>. <em>écrire</em> des pdf à partir de markdown fonctionne sur toute installation, sans extra.

## merirmaid
name: merirmaid
path: *.merirmaid

### what
la variante enough d'un diagramme <a href="https://mermaid.js.org/" target="_blank" rel="noopener">Mermaid</a> : une source de diagramme en texte brut avec un petit en-tête, rendue en direct sous forme d'image dans le navigateur (organigrammes, diagrammes de séquence, machines à états, diagrammes ER — tout ce que Mermaid prend en charge). deux sortes : un diagramme <em>wip</em> que vous pouvez retoucher, et un <em>mirror</em> qui reflète une structure existante (comme le contenu d'un cachebox) et reste en lecture seule.

### how
demandez à l'agent de dessiner ou réviser un diagramme — il écrit la source <code>.merirmaid</code> ; ouvrir le fichier le rend. dans un diagramme wip, vous pouvez cliquer sur le texte d'un nœud pour modifier l'étiquette sur place (avec un compteur de caractères en direct) ; les changements structurels passent par l'agent via la pastille de discussion. les nœuds peuvent pointer vers d'autres diagrammes ou documents — cliquez dessus pour les suivre, avec un fil d'ariane pour revenir en arrière. un diagramme cassé affiche l'erreur plus la source brute, jamais un panneau vide. les diagrammes mirror affichent un badge « mirror » au lieu de poignées de modification.

### ideas
- demandez à l'agent de diagrammer un processus ou une architecture sur lesquels vous réfléchissez, puis affinez-le en conversation.
- reliez un ensemble de diagrammes entre eux avec des nœuds cliquables pour construire une carte navigable.
- associez-le aux girraphs : un girraph pour l'argument, un merirmaid pour le flux.

## cacheawl
name: cacheawl
path: ~/enough/cacheawl/

### what
le dépôt global à la machine des <em>cacheboxes</em> — des dossiers de premier niveau contenant du texte que vous voulez garder pour toujours, ou des répliques mises en cache ingérées depuis un chemin local, un site web, ou des articles wikipédia. partagé entre tous les projets et caché des arborescences de projet. c'est là que vit désormais l'ancienne bibliothèque <code>infoworld</code>.

### how
ouvrez le mode cacheawl depuis la barre supérieure pour la vue à deux volets (projet ↔ cacheboxes) : glissez pour copier un fichier entre les deux, shift-glissez pour déplacer, et utilisez la barre d'ingestion pour demander à l'agent de tirer une source dans une box. ou parlez directement à l'agent — il peut lister, créer, et ingérer dans les box quand l'interrupteur broker « cacheawl tools » est activé (les ingestions d'url respectent aussi vos interrupteurs fetch_url). chaque box affiche un diagramme généré automatiquement de son contenu (<code>_cachebox.merirmaid</code>, lecture seule) et garde des métadonnées cachées auxquelles vous ne touchez pas.

### ideas
- ingérez un site de documentation ou un dossier de notes pour que l'agent puisse y travailler hors ligne.
- déplacez un artefact terminé dans un cachebox pour le sortir du projet de travail tout en le gardant accessible partout.
- double-cliquez sur le diagramme d'une box pour voir sa forme d'un coup d'œil dans la visionneuse merirmaid.

## footnotes
name: notes de bas de page
path: (inside your markdown files)

### what
de vraies notes de bas de page pour les textes en cours. écrivez <code>[^1]</code> dans la prose et mettez <code>[^1]: la note elle-même</code> en bas du fichier — en vue de lecture, chaque note apparaît comme une petite carte dans la marge, alignée avec son marqueur. les cartes se modifient sur place : retournez-en une pour l'éditer, enregistrez ou annulez, terminé. le fichier sur le disque reste du markdown simple et portable.

### how
dans l'éditeur, tapez <code>[^]</code> et ça devient automatiquement le numéro de note suivant, ou utilisez le bouton insérer-une-note de la barre d'outils à l'emplacement du curseur. insérez une nouvelle note entre deux existantes et tout ce qui suit se renumérote tout seul, définitions comprises. les notes nommées comme <code>[^aside]</code> sont laissées exactement telles que vous les avez écrites. un marqueur sans définition affiche encore une carte vide — tapez dedans et l'enregistrement écrit la définition pour vous.

### ideas
- rédigez avec des marqueurs <code>[^]</code> rapides et remplissez les corps plus tard depuis les cartes en marge.
- la numérotation des notes reste propre quel que soit l'ordre dans lequel vous écrivez — la pagination s'appuie là-dessus, si bien qu'un texte à la « prose achevée » n'a besoin d'aucune passe de nettoyage.

## paginate
name: paginer
path: (next to the markdown it came from)

### what
transforme un texte achevé en un pdf proprement composé — de vraies pages, des chapitres qui repartent à neuf, des notes de bas de page réconciliées où vous les voulez (sur la page, à la fin de chaque chapitre, ou rassemblées dans une section de notes finale). le markdown reste l'original modifiable ; le pdf est un instantané daté à côté, par ex. <code>book-2026-08-23.pdf</code>.

### how
ouvrez un fichier markdown en vue de lecture et appuyez sur le bouton paginer dans la barre d'outils. choisissez une taille de page (letter, a4, format poche… ou personnalisée), portrait ou paysage, une des polices fournies, une marge, et en option des numéros de page et des en-têtes courants (votre texte, ou le nom du chapitre). 2 par page met deux pages par feuille ; livret les entrelace pour qu'une impression recto verso se plie en un livre agrafable. « apporter le pdf dans enough » ajoute une vue page par page avec un défilement aux flèches et le plein écran. chaque pdf exporté transporte secrètement son propre markdown source, si bien qu'en réimporter un dans un projet restaure le texte — notes de bas de page comprises — à l'identique.

### ideas
- relisez un brouillon au format poche avec des notes en fin de chapitre avant de décider de la forme finale.
- imprimez un livret pour un texte court : mise en page livret, demi-letter, agrafez le résultat.
- envoyez le pdf à quelqu'un ; s'il revient un jour sans l'original, le réimporter récupère le markdown parfaitement.
