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
votre copie locale et hors ligne (d'une tranche) de wikipédia anglais — une seule archive Kiwix ZIM lue sur place, jamais extraite, si bien que le gestionnaire de fichiers ne montre que les articles que vous enregistrez explicitement. le bouton 🚰 ouvre un lecteur façon navigateur avec recherche plein texte, liens croisés, un dé à article aléatoire, une pastille de discussion readvisor, des commentaires, et un unique <strong>bouton enregistrer</strong> dont le menu propose deux destinations (le <code>wiki/</code> de ce projet, ou le cachebox global <code>~/enough/cacheawl/wiki/</code> partagé entre les projets). vos readvisors peuvent chercher et lire toute l'archive via leurs outils wiki.

### how
le premier clic sur 🚰 lance l'assistant de configuration : choisissez une taille (top 1 M d'articles sans images ≈ 16 Go par défaut ; anglais complet ≈ 49 Go ; options plus petites aussi), choisissez un dossier de stockage (les disques externes conviennent), confirmez, et laissez tourner le téléchargement reprenable — pause, quitter, reprendre à tout moment. vous pouvez garder <em>plusieurs installations</em> à différents endroits (par exemple l'archive complète sur un disque externe plus une petite sur le disque interne) et basculer entre elles dans la liste des installations ⚙ ; si un disque est débranché, son installation s'affiche simplement comme inaccessible jusqu'à son retour. une fois installé, demandez à votre readvisor en chef de lancer un <strong>wikisink</strong> pour rafraîchir vos articles enregistrés/commentés (« surveillés ») depuis wikipédia en direct et obtenir un rapport : changements sur les articles surveillés, pics d'édition, articles qui montent ou descendent en popularité, et suppressions suspectes. le bouton 🛡 sur n'importe quel article est la <em>dérogation de suppression</em> : garder votre copie locale pour toujours, exclue des mises à jour. ⚙ ouvre le gestionnaire d'installations, y compris le remplacement de l'archive de base quand un instantané plus récent sort. inutile d'aller le chercher : quand une nouvelle version de votre variante existe, une petite pastille apparaît dans la barre d'outils du lecteur (<code>nouvel instantané : date · taille</code>) — cliquez dessus, confirmez la taille, et la même mise à niveau sur place s'exécute, téléchargeant d'abord et substituant seulement une fois terminé. la vérification a lieu au plus une fois par jour, ne bloque jamais le lecteur, et reste silencieuse quand vous êtes hors ligne.

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
- vos readvisors lisent les articles via leurs outils wiki (extraction de texte propre), ils peuvent donc s'appuyer aussi bien sur les articles enregistrés que sur ceux de l'archive.
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
- interrogez votre readvisor en chef sur un passage surligné via le 🤖 du popup de sélection — le passage est cité automatiquement dans la discussion.

## paradigm-active
name: paradigme
path: rness/active-paradigm

### what
le cadre de raisonnement dans lequel vos readvisors travaillent actuellement. un seul paradigme est actif à la fois ; cliquez sur un autre pour en changer. le paradigme actif est chargé en entier dans le prompt système à chaque tour, et votre readvisor en chef voit aussi un bref catalogue des autres paradigmes disponibles afin de pouvoir suggérer (ou déclencher) un changement quand le travail en tirerait profit.

### how
cliquez sur ● à côté d'un paradigme pour l'activer pour ce projet. le choix est enregistré dans <code>rness/active-paradigm</code>. un changement initié par votre readvisor en chef passe aussi par l'écriture de ce fichier, et prennent effet au tour suivant. ajoutez de nouveaux paradigmes en déposant un fichier markdown dans <code>~/enough/defaults/paradigms/</code> (ou dans le <code>rness/paradigms/</code> de votre projet pour des paradigmes locaux). un bloc de frontmatter YAML en tête — <code>name:</code> et <code>description:</code> — indique à vos readvisors à quoi sert le paradigme.

### ideas
- Paradigmes disponibles dans ce projet : {{paradigms-list}}
- écrivez un paradigme pour chaque mode de travail distinct (recherche vs. écriture, exploration vs. exécution) et passez de l'un à l'autre au fil de la journée.
- une description de paradigme répond essentiellement à « quand devrais-je m'en servir » — écrivez-la pour votre readvisor en chef, puisque c'est le signal qu'il lit pour recommander un changement.

## requests
name: requêtes/
path: rness/requests/

### what
des conteneurs persistants de tâches et sous-tâches. chaque requête est un fichier markdown qui capture l'objectif de votre demande, le raisonnement de votre readvisor en chef jusque-là, et un bloc Continuation pour que le travail puisse reprendre après une remise à zéro du contexte — c'est l'unité d'effort de longue durée dans enough. elles aident aussi à poursuivre le travail si vous atteignez une limite de fenêtre de contexte. les requêtes terminées vivent aux côtés des actives dans <code>rness/requests/done/</code>.

### how
de nouvelles requêtes apparaissent automatiquement dans <code>rness/requests/</code> au fil de votre travail avec votre readvisor en chef — cliquez sur n'importe quel fichier dans l'arborescence du projet pour le voir dans le panneau de fichier. de là, vous pouvez <em>marquer comme terminé</em> (le fichier se déplace vers <code>rness/requests/done/</code>) ou <em>personnaliser</em>. pour démarrer une requête manuellement, déposez un fichier markdown dans <code>rness/requests/</code> avec un bref objectif en tête.

### ideas
- traitez une requête comme un projet de longue haleine — décomposez une intention vague en une requête et laissez votre readvisor en chef l'étoffer sur plusieurs sessions.
- parcourez <code>rness/requests/done/</code> comme un journal de ce que vous avez réellement accompli — c'est l'enregistrement le plus honnête de ce que vous et votre readvisor en chef avez réellement livré.
- aux points de contrôle de remise à zéro automatique du contexte, votre readvisor en chef écrit un bloc Continuation dans la requête active — lisez-le avant de reprendre si vous voulez réorienter les choses.

## skills
name: compétences
path: rness/skills/

### what
des interrupteurs par projet pour les compétences — des unités de capacité ciblée liées par symlink depuis <code>~/enough/defaults/skills/</code>. les compétences actives ajoutent du vocabulaire, des recettes, ou des comportements que vos readvisors iront chercher en conversation. les compétences fournies avec enough sont <em>de confiance</em> et s'activent instantanément ; tout ce qui se trouve ailleurs dans <code>rness/skills/</code> — téléchargé, offert, ou écrit pour vous par votre propre readvisor en chef — est <em>non vérifié</em> tant que ça n'a pas été lu, et la première fois que vous l'activez, enough l'audite avant qu'un seul mot n'atteigne vos readvisors.

### how
cliquez sur ● / ○ pour activer ou désactiver une compétence pour ce projet. vous pouvez ajouter des compétences locales au projet dans <code>rness/skills/</code> — les états des compétences sont enregistrés par projet. pour installer de nouvelles compétences globalement, déposez un dossier dans <code>~/enough/defaults/skills/</code> ; elle apparaît dans tous les projets (désactivée par défaut). modifiez une compétence globale à la source et le changement se propage partout où elle est liée par symlink. une compétence non vérifiée affiche une petite marque à côté de son nom qui progresse de <em>non vérifié</em> → <em>audit en cours…</em> → <em>audité</em> ; si l'audit trouve quelque chose, la ligne affiche <em>signalé</em>, la compétence reste désactivée, et vous obtenez deux boutons — <em>lire le rapport</em> (ouvre le rapport complet) et <em>activer quand même</em> (demande confirmation, puis enregistre la décision comme étant la vôtre). les rapports atterrissent dans <code>rness/io/output/analyzer/audits/&lt;skill&gt;/</code>. modifiez ensuite les fichiers d'une compétence et elle est relue à la prochaine activation.

### ideas
- Compétences disponibles dans ce projet : {{skills-list}}
- construisez des compétences globales ou locales au projet pour capturer votre style maison ou les conventions de votre domaine.
- désactivez tout pour une « conversation pure » — parfois le modèle a plus d'espace pour des éclairs de lucidité émergents sans aucun échafaudage.
- demandez à votre readvisor en chef d'<em>auditer</em> une compétence avant de l'activer (le quatrième mode d'analyzer) — le même rapport que l'audit au premier usage écrit, juste selon votre propre calendrier.

## roles
name: readvisors
path: rness/readvisors/

### what
les autres lecteurs de la pièce. un readvisor est un dossier contenant AGENT.md (qui il est) et MOTIVATION.md (ce qui lui importe) — une seule forme, des intertitres fixes, pour que chaque readvisor fonctionne de la même manière malgré sa voix et ses manies. activés ici, ils sont fondus dans la voix unique de votre readvisor en chef dans la conversation ordinaire ; dans une composure de type conseil, chacun parle séparément, sous son propre nom.

### how
cliquez sur ● / ○ pour en activer ou en désactiver un pour ce projet. l'infobulle de chaque ligne indique son origine : ceux <em>livrés</em> viennent avec enough (<code>defaults/readvisors/</code>) et n'ont pas de bouton de suppression ; ceux <em>globaux</em> sont les vôtres, vivent dans <code>~/enough/readvisors/</code> et apparaissent dans tous les projets de cette machine ; ceux <em>du projet</em> n'appartiennent qu'à ce dossier (<code>rness/readvisors/&lt;name&gt;/</code>). le × sur une ligne globale ou de projet la supprime, après confirmation. la compétence <em>readvisory</em> vous interroge et en écrit un nouveau.

### ideas
- Readvisors disponibles dans ce projet : {{roles-list}}
- construisez un « canard en plastique » qui pose des questions socratiques au lieu de répondre.
- utilisez les fichiers de votre base de connaissances avec le paradigme <em>workflow-design</em> pour façonner un expert du domaine (juridique, design, rédaction).
- activez-en deux qui ne sont pas d'accord, puis tenez un conseil et laissez-les en débattre sur le canevas.

## rness
name: rness/
path: rness/

### what
le système externalisé du projet. rness/ est l'endroit où vivent la config, les instructions, les fichiers de connaissance et les journaux d'historique de chaque projet — tout ce que vos readvisors utilisent pour ce projet. il se trouve à la racine du projet pour que vous puissiez le modifier directement avec n'importe quel gestionnaire de fichiers ou éditeur ; l'interface d'enough affiche aussi son contenu dans la barre latérale.

### how
certains contenus sont des liens symboliques vers <code>~/enough/defaults/</code> et se mettent à jour de façon centralisée. pour diverger sur un projet, ouvrez un fichier et cliquez sur <em>personnaliser</em> — il devient une copie locale au projet. ajoutez librement de nouveaux fichiers via la conversation ou le gestionnaire de fichiers de votre système ; vos readvisors verront tout fichier ajouté localement dès le tour suivant.

### ideas
- apprenez à connaître les composants qui font tourner votre flux de travail enough et modifiez-les comme bon vous semble.
- traitez-le comme une documentation vivante — qu'aurait besoin de savoir un nouveau coéquipier, ou un nouveau readvisor ?
- élaguez périodiquement les connaissances obsolètes pour que vos readvisors ne citent pas des décisions caduques.

## agent-md
name: AGENT.md
path: rness/AGENT.md

### what
qui est votre readvisor en chef et comment il opère ici : ses instructions de travail pour ce projet, utilisées à chaque tour aux côtés de MOTIVATION.md. tout ce qui s'y trouve façonne la manière dont il parle, ce qu'il fait, et ce qu'il évite.

### how
cliquez sur le fichier pour le consulter ; appuyez sur <em>personnaliser</em> pour créer une copie locale au projet et la modifier. ou ouvrez <code>rness/AGENT.md</code> dans n'importe quel éditeur — les changements enregistrés prennent effet au message suivant.

### ideas
- ajoutez des garde-fous propres au projet (par ex. « toujours revérifier l'orthographe et l'exactitude avant de finaliser une modification »).
- listez les conventions de nommage de votre projet pour que votre readvisor en chef n'ait pas à deviner (ou à hallucinnover).
- codifiez le style de collaboration que vous voulez — laconique, exploratoire, déférent, direct.

## motivation-md
name: MOTIVATION.md
path: rness/MOTIVATION.md

### what
le « pourquoi » de votre readvisor en chef pour ce projet — valeurs, priorités, et objectifs au-delà de la simple liste de tâches. utilisé aux côtés d'AGENT.md à chaque tour.

### how
comme pour AGENT.md — cliquez pour prévisualiser, personnalisez pour obtenir une copie locale au projet, ou modifiez le fichier directement.

### ideas
- explicitez les compromis qui comptent pour vous : l'exactitude plutôt que la vitesse, la concision plutôt que l'exhaustivité, etc.
- nommez, dans vos propres mots, l'expérience utilisateur que le projet vise.
- décrivez à quoi ressemble « terminé » — votre readvisor en chef calibrera là-dessus son sens de la progression.

## paradigms
name: paradigmes/
path: rness/paradigms/

### what
l'ensemble complet des cadres de raisonnement disponibles dans ce projet. chaque paradigme est un fichier markdown avec un bloc de frontmatter YAML (<code>name</code> + <code>description</code>) et un corps décrivant comment aborder le travail — heuristiques, critères de décision, quand demander plutôt qu'agir. un seul est actif à la fois (voir la section <strong>paradigme</strong> en haut de la barre latérale pour en changer).

### how
lié par symlink depuis <code>~/enough/defaults/paradigms/</code>. modifiez-le globalement pour changer le comportement dans tous les projets ; cliquez sur <em>personnaliser</em> sur n'importe quel fichier pour le forker rien que pour ce projet. de nouveaux paradigmes peuvent être ajoutés simplement en déposant un fichier markdown dans le dossier des défauts — donnez-lui un <code>name:</code> et une <code>description:</code> en frontmatter pour que votre readvisor en chef sache quand le recommander.

### ideas
- Paradigmes disponibles dans ce projet : {{paradigms-list}}
- écrivez un paradigme pour chaque mode de travail distinct (recherche vs. écriture, exploration vs. exécution) et passez de l'un à l'autre au fil de la journée.
- une description de paradigme répond essentiellement à « quand devrais-je m'en servir » — écrivez-la pour votre readvisor en chef, puisque c'est le signal qu'il lit pour recommander un changement.

## policies
name: politiques/
path: rness/policies/

### what
des règles strictes que vos readvisors doivent suivre — quels outils utiliser, quels fichiers ils peuvent lire ou écrire, comment formater les requêtes, comment gérer la pression sur la fenêtre de contexte, et quels chemins sont sur liste blanche.

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
des connaissances propres au projet qui n'ont pas leur place dans <code>rness/io/</code> ou <code>~/enough/infoworld/</code> : contient toujours <code>project-profile.md</code> (des notes vivantes que votre readvisor en chef tient sur ce projet — vos préférences et votre style de travail tels qu'observés ici, les personnes / fichiers récurrents, les conventions adoptées) et <code>session-logs/</code> (le prompt et la réponse de chaque tour, enregistrés en markdown).

### how
<code>project-profile.md</code> est injecté dans le prompt système à chaque tour — vous et votre readvisor en chef pouvez tous deux le modifier. les journaux de session sont en ajout seul. ajoutez de nouveaux sous-dossiers pour toute mémoire locale au projet que vous voulez voir consultée par vos readvisors.

### ideas
- tenez un sous-dossier glossaire pour le jargon propre au projet.
- laissez votre readvisor en chef écrire un fichier « leçons apprises » au fil de vos itérations communes.
- archivez périodiquement les anciens journaux de session pour que les recherches de vos readvisors restent rapides.

## io
name: io/
path: rness/io/

### what
un espace au niveau du projet pour les fichiers que vos readvisors lisent (<code>input/</code>) ou dans lesquels ils écrivent (<code>output/</code>). utile quand vous voulez qu'un fichier soit traité sans polluer la racine du projet.

### how
déposez des fichiers dans <code>rness/io/input/</code> et vos readvisors les verront. tout ce qu'ils génèrent atterrit dans <code>rness/io/output/</code> — passez en revue et déplacez ce que vous voulez garder, puis videz le reste. les documents comptent aussi : un fichier word ou un pdf déposé ici s'ouvre comme un jumeau markdown et se lit comme n'importe quel autre fichier, pour vous comme pour eux.

### ideas
- déposez un CSV ou une transcription dans <code>input/</code> et demandez à votre readvisor en chef de résumer.
- déposez le pdf que quelqu'un vous a envoyé par mail dans <code>input/</code>, cliquez dessus, et lisez-le en markdown — l'original reste exactement tel qu'il est arrivé.
- rassemblez plusieurs brouillons dans <code>output/</code> et choisissez le meilleur (ou demandez au modèle de les évaluer les uns contre les autres).
- videz les deux périodiquement — vos readvisors n'ont pas besoin du brouillon d'hier dans leur contexte.

## infoworld
name: cacheawl
path: ~/enough/cacheawl/

### what
le dépôt de fichiers global à la machine, partagé entre tous les projets enough. (ceci remplace l'ancienne bibliothèque <code>infoworld/</code> — au premier lancement de cette version, vos dossiers <code>personal/</code>, <code>public/</code> et <code>wiki/</code> ont été déplacés ici, chacun devenant un cachebox.) un <em>cachebox</em> est un dossier de premier niveau dans le dépôt : soit du texte brut que vous voulez garder pour toujours, soit une « réplique mise en cache » ingérée depuis un chemin local, un site web, ou un ensemble d'articles wikipédia. le dépôt est caché de l'arborescence de chaque projet et géré via le mode cacheawl + les outils de cachebox de vos readvisors.

### how
ouvrez le mode cacheawl (le bouton cacheawl de la barre supérieure) pour une vue à deux volets : votre projet d'un côté, les cacheboxes de l'autre. glissez un fichier d'un côté à l'autre pour le copier, shift-glissez pour le déplacer ; la barre d'ingestion compose une requête à votre readvisor en chef pour aller chercher un chemin/site/sujet wiki. ou demandez simplement dans le panneau — vos readvisors peuvent lister, créer, et ingérer dans les cacheboxes (soumis à l'interrupteur broker « cacheawl tools »). chaque box porte un diagramme <code>_cachebox.merirmaid</code> généré automatiquement à partir de son contenu (lecture seule — il se régénère depuis les fichiers) et des métadonnées cachées ; vous ne modifiez jamais ça directement.

### ideas
- ingérez un site de documentation sur une faible profondeur pour que vos readvisors puissent s'appuyer dessus entièrement hors ligne.
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
- demandez à votre readvisor en chef de lire un document par son nom — <code>read_file</code> sur <code>report.pdf</code> lui donne le jumeau, en en convertissant un d'abord s'il n'y en a pas encore.
- lire des pdf, présentations powerpoint et classeurs excel nécessite l'<strong>extra pdf</strong> (⚙ fenêtre ui → extras) : environ 250 Mo à télécharger, environ 1 Go installé, plus environ 0,7 Go de modèles de document dans <code>~/enough/weights/docling/</code>. <em>écrire</em> des pdf à partir de markdown fonctionne sur toute installation, sans extra.

## merirmaid
name: merirmaid
path: *.merirmaid

### what
la variante enough d'un diagramme <a href="https://mermaid.js.org/" target="_blank" rel="noopener">Mermaid</a> : une source de diagramme en texte brut avec un petit en-tête, rendue en direct sous forme d'image dans le navigateur (organigrammes, diagrammes de séquence, machines à états, diagrammes ER — tout ce que Mermaid prend en charge). deux sortes : un diagramme <em>wip</em> que vous pouvez retoucher, et un <em>mirror</em> qui reflète une structure existante (comme le contenu d'un cachebox) et reste en lecture seule.

### how
demandez à votre readvisor en chef de dessiner ou réviser un diagramme — il écrit la source <code>.merirmaid</code> ; ouvrir le fichier le rend. dans un diagramme wip, vous pouvez cliquer sur le texte d'un nœud pour modifier l'étiquette sur place (avec un compteur de caractères en direct) ; les changements structurels passent par votre readvisor en chef via la pastille de discussion. les nœuds peuvent pointer vers d'autres diagrammes ou documents — cliquez dessus pour les suivre, avec un fil d'ariane pour revenir en arrière. un diagramme cassé affiche l'erreur plus la source brute, jamais un panneau vide. les diagrammes mirror affichent un badge « mirror » au lieu de poignées de modification.

### ideas
- demandez à votre readvisor en chef de diagrammer un processus ou une architecture sur lesquels vous réfléchissez, puis affinez-le en conversation.
- reliez un ensemble de diagrammes entre eux avec des nœuds cliquables pour construire une carte navigable.
- associez-le aux girraphs : un girraph pour l'argument, un merirmaid pour le flux.

## cacheawl
name: cacheawl
path: ~/enough/cacheawl/

### what
le dépôt global à la machine des <em>cacheboxes</em> — des dossiers de premier niveau contenant du texte que vous voulez garder pour toujours, ou des répliques mises en cache ingérées depuis un chemin local, un site web, ou des articles wikipédia. partagé entre tous les projets et caché des arborescences de projet. c'est là que vit désormais l'ancienne bibliothèque <code>infoworld</code>.

### how
ouvrez le mode cacheawl depuis la barre supérieure pour la vue à deux volets (projet ↔ cacheboxes) : glissez pour copier un fichier entre les deux, shift-glissez pour déplacer, et utilisez la barre d'ingestion pour demander à votre readvisor en chef de tirer une source dans une box. ou dites-le simplement dans le panneau — vos readvisors peuvent lister, créer, et ingérer dans les box quand l'interrupteur broker « cacheawl tools » est activé (les ingestions d'url respectent aussi vos interrupteurs fetch_url). chaque box affiche un diagramme généré automatiquement de son contenu (<code>_cachebox.merirmaid</code>, lecture seule) et garde des métadonnées cachées auxquelles vous ne touchez pas.

### ideas
- ingérez un site de documentation ou un dossier de notes pour que vos readvisors puissent y travailler hors ligne.
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

## composure
name: composure
path: rness/io/composure/

### what
le canevas qui est toujours là, derrière tout le reste — la couche de base de la fenêtre, pas un mode qu'on ouvre et qu'on quitte. une <strong>composure</strong> est un fichier <code>.comp</code> : des boîtes de texte (les <em>modules</em>) et de l'encre à main levée sur un plan de travail sans bord que vous faites glisser et que vous zoomez. elle s'ouvre dans n'importe quel navigateur comme une page ordinaire, sans aucun enough installé, parce que le fichier lui-même est du html tout simple.

### how
la barre d'outils court en haut : le titre (pour le renommer, tapez dedans puis cliquez ailleurs), le sélecteur lecture/édition, les outils, annuler/rétablir, le groupe de zoom, la recherche, le panneau des commentaires et le menu des composures. faites glisser à deux doigts, avec la barre d'espace enfoncée ou avec le bouton du milieu ; zoomez par pincement, ⌘-molette, ⌘+ / ⌘− / ⌘0, ou « ajuster ». il n'y a pas de bouton enregistrer — tout s'écrit au fil de l'eau, et une composure que vous ouvrez sans jamais y toucher n'écrit aucun fichier. dézoomez assez loin et chaque module se replie sur sa <em>face</em> : son titre, aussi grand que la boîte le permet, le corps en faux-texte — soixante cartes se lisent alors comme soixante titres.

### ideas
- gardez un tableau par projet : la carte que vous regardez avant de vous mettre à écrire.
- un module <code>.comp</code> qui pointe vers un autre <code>.comp</code> transforme un tableau en descente par paliers : un clic échange le canevas sous vos pieds.
- sélectionnez un passage dans un module et il part avec votre prochain message à votre readvisor, encadré et étiqueté.

## composure-modules
name: modules
path: (inside a .comp file)

### what
les boîtes posées sur une composure. un module <strong>texte</strong>, c'est de l'écriture — titres, listes, listes à cocher, citations, liens, surlignages — avec autant de pages que vous voulez à l'intérieur. les cinq autres pointent vers quelque chose : un <strong>fichier</strong> de ce projet, un article <strong>wikisink</strong>, un <strong>lien vers le web</strong>, une <strong>page web</strong> en cache, ou une <strong>image</strong>. un module qui pointe affiche un aperçu en direct pendant que vous lisez, et un clic ouvre la vraie chose.

### how
le bouton d'ajout de module ouvre une courte liste des six types. quand un module est sélectionné en mode édition, l'inspecteur apparaît à côté : pastille de fond, taille du texte, pages, premier plan/arrière-plan, le champ propre au type (un sélecteur de fichier, une recherche d'article, une adresse), et un bouton de commentaire. glissez pour déplacer, glissez une poignée pour redimensionner, les flèches pour décaler finement (maj pour un pas plus grand), suppr pour retirer — avec un avertissement d'abord s'il y a du texte dedans, et ⌘Z pour revenir en arrière. un texte qui déborde de sa boîte vous propose une nouvelle page plutôt que de grandir en silence.

### ideas
- donnez un titre à un module et il garde son nom quand vous dézoomez au-delà de la taille de lecture.
- les pastilles <code>encre</code> et <code>transparent</code> servent à la structure — une carte sombre pour une ligne de titre, une transparente pour une étiquette qui n'est pas une carte du tout.
- pointez un module vers un fichier que vous rouvrez sans arrêt ; le tableau devient un bureau avec les bons papiers déjà posés dessus.

## composure-tools
name: outils
path: (the composure toolbar)

### what
quatre outils, et ils n'existent que pendant l'édition : le <strong>pointeur</strong> (V) sélectionne, déplace, redimensionne et trace un rectangle de sélection ; le <strong>texte</strong> (T) place le curseur dans un module ; le <strong>crayon</strong> (P) dessine ; la <strong>gomme</strong> (E) efface. l'encre, ce sont des polylignes à main levée posées sur le plan de travail, sous les modules : une note peut donc traverser trois cartes et une flèche en relier deux.

### how
avec le crayon, dessinez, tout simplement — le trait est lissé et simplifié quand vous relâchez. maintenez <strong>maj</strong> pendant que vous glissez et vous obtenez un segment droit terminé par une pointe de flèche. la gomme est un cercle qui garde la même taille à l'écran quel que soit le zoom ; la faire passer sur un trait retire la partie sous le cercle et laisse les deux bouts comme deux traits séparés, et ⌘Z remet le trait d'un seul tenant. attrapez un trait avec le pointeur en cliquant juste à côté — l'inspecteur propose alors les cinq couleurs d'encre, et suppr le retire. les traits s'amincissent plus lentement que le dessin ne rétrécit : un croquis vu de loin se lit encore comme un croquis.

### ideas
- entourez les trois cartes qui vont ensemble avant de décider comment s'appelle le groupe.
- tracez des flèches en maj+glisser entre les modules pour montrer ce qui suit quoi, puis déplacez les modules ; la flèche reste là où vous l'avez tracée, ce qui est en général la réponse honnête.
- dessinez en rouge sur un tableau que vous relisez, et effacez les marques une fois que vous vous en êtes occupé.

## journal
name: journal
path: rness/io/composure/

### what
un form de composure pour tenir un registre daté. un module, une entrée par page. ouvrir un journal vous pose sur la page d'<em>aujourd'hui</em>, curseur déjà dedans — et cette page n'existe qu'en mémoire jusqu'à ce que vous tapiez quelque chose, donc ouvrir le journal puis se raviser ne laisse rien derrière.

### how
écrivez. l'entrée s'enregistre au fil de l'eau, et si vous partez sans la classer, le journal rouvre sur ce même brouillon inachevé. quand l'entrée est finie, appuyez sur <strong>classer cette entrée</strong> : la page est estampillée de la date et devient définitivement en lecture seule — enough refusera de la modifier ensuite, et le curseur n'y entrera plus. classer vous fait passer à une page neuve pour la fois suivante. refeuilleter les entrées classées ne risque rien : tourner une page où vous n'avez pas écrit n'enregistre rien du tout. vous pouvez toujours commenter un texte classé, et c'est bien tout l'intérêt de le classer.

### ideas
- classez à la fin d'une séance de travail plutôt qu'à la fin d'une journée ; la date est un fait, pas une échéance.
- commentez une vieille entrée classée quand elle s'avère avoir été fausse — le registre reste, et la seconde pensée s'assied à côté.
- demandez à votre readvisor de lire le journal quand vous voulez un résumé de là où un long travail est réellement passé.

## readvisor-panel
name: panneau readvisor
path: (the right-hand panel)

### what
la conversation, dans une colonne à elle, à côté de ce sur quoi vous travaillez. votre <strong>readvisor en chef</strong> est nommé en haut, avec les autres readvisors que vous avez activés listés à côté de lui — en conversation ordinaire, ils répondent d'une seule voix, nourrie de toutes ces perspectives.

### how
⌘/ l'ouvre et le ferme ; ⇧⌘/ lui donne toute la fenêtre et ⌘/ le ramène. il se tient à côté du canevas ou à côté de n'importe quel mode ouvert : vous n'avez donc jamais à fermer ce que vous lisez pour poser une question dessus. sélectionnez du texte — dans un document, dans un article wikisink, dans un module de composure — et une pastille apparaît au-dessus de la zone de message, montrant exactement ce qui va être joint ; × la retire. quand un tour se termine alors que le panneau est fermé, un point apparaît sur son bouton dans la barre du haut.

### ideas
- laissez-le ancré pendant que vous écrivez et posez vos questions en passant ; c'est un collègue au bureau d'à côté, pas une fenêtre qu'on ouvre.
- joignez une sélection plutôt que de la décrire — les mots exacts traversent, encadrés, avec leur provenance.
- donnez-lui toute la fenêtre quand vous voulez lire une longue réponse correctement, puis remettez-le en colonne pour agir dessus.

## council
name: conseil
path: (a composure whose form is council)

### what
plusieurs readvisors et vous, en train de réfléchir à une seule chose chacun son tour, par écrit, sur le canevas. un conseil est une composure ordinaire, avec le brief en haut et une carte par intervention en dessous, teintée selon qui parle et coiffée d'un nom et d'un numéro de tour. les interventions appartiennent au moteur : vous pouvez les déplacer, les restyler, dessiner par-dessus et les commenter, mais pas les réécrire.

### how
remplissez le brief — entrée, paramètres, contraintes, sortie souhaitée — cochez qui est dans la salle, donnez à qui vous voulez une <em>charge</em> d'une ligne s'il est là pour quelque chose de précis (« garde la continuité », « défend le lecteur »), fixez les tours max, et appuyez sur convoquer. ensuite, pilotez : <em>tour suivant</em> prend une intervention, <em>faire un tour</em> fait le tour complet de la table, <em>aller jusqu'au bout</em> va jusqu'au plafond de tours, <em>mettre en pause</em> l'arrête, <em>conclure</em> demande la décision au chef. la zone de saisie en bas est à vous : ce que vous dites prend le créneau suivant sans coûter son tour à personne, et <code>/pal</code> tapé là envoie une seule question distillée au modèle cloud et en rapporte la réponse sous forme d'intervention. conclure écrit ce que le conseil a décidé dans la forme que vous avez choisie — une carte surlignée, un fichier markdown au chemin de votre choix, ou toute une nouvelle composure de cartes à côté de celle-ci — et exporte la transcription vers <code>rness/knowledge/councils/</code>. un conseil conclu peut être <em>reconvoqué</em> : un nouveau conseil avec la même assemblée, les mêmes charges et ce que celui-ci a décidé comme point de départ.

### ideas
- confiez la thèse inverse à un readvisor et voyez si elle survit au contact des autres.
- une charge est le moyen le moins cher d'empêcher trois readvisors de dire la même chose de trois façons.
- réglez la sortie sur un document quand la décision doit quitter le canevas sous forme de fichier citable, ou sur une composure quand ce que vous voulez est la forme de la décision plutôt que ses paragraphes.
- dites quelque chose vous-même dès qu'un conseil se met à tourner en rond ; une interjection coûte moins cher qu'un tour de plus.
- reconvoquez plutôt que de tout recommencer quand la réponse était juste mais pas finie.

## chief-readvisor
name: readvisor en chef
path: (the name on every reply)

### what
le seul readvisor à qui vous parlez en permanence. il a un nom — Ed d'origine — et ce nom signe chaque réponse de la conversation, coiffe le panneau readvisor, et parle en premier dans un conseil. le nom est global : un seul par machine, rangé à côté de votre thème et de votre langue d'interface plutôt qu'à l'intérieur d'un projet.

### how
appuyez sur le bouton de renommage à côté du × dans cet en-tête, tapez un nouveau nom et enregistrez. de 1 à 24 caractères : lettres et chiffres, plus l'espace, le trait d'union, l'apostrophe et le point, dans l'écriture que vous voulez. toutes les surfaces qui affichent le nom se mettent à jour immédiatement, sans rechargement. un conseil qui a déjà parlé garde le nom dont ses interventions ont été signées — les interventions sont attribuées par nom, et un renommage en cours de route se lirait comme deux personnes différentes.

### ideas
- choisissez quelque chose que vous diriez à voix haute ; vous allez le lire toute la journée.
- renommez avant de convoquer un conseil, pas pendant.

## pal
name: pal
path: (the OPRO-API model slot)

### what
une seule question, envoyée dehors, à découvert. un <strong>pal</strong>, c'est le modèle cloud que vous avez déjà configuré dans l'emplacement OPRO-API, joint une fois, à la main, depuis un tour par ailleurs entièrement local. il n'y a pas de réglage pal, pas de compte pal et pas de second interrupteur : si l'emplacement cloud marche, un pal marche, et s'il ne marche pas, l'explication habituelle du broker est toute l'histoire. taper <code>/pal</code> est le consentement — il n'y a pas d'étape de confirmation, parce qu'une étape de confirmation qui apparaît à chaque fois est un bouton que les gens apprennent à cliquer. ce qui la remplace, c'est que l'invite qui quitte cette machine vous est montrée mot pour mot, avant la réponse, à chaque fois, en direct et après un rechargement.

### how
commencez un message par <code>/pal</code> et le reste est la demande : <code>/pal quel est l'état de l'art de la reconnaissance vocale sur l'appareil ?</code>. tapez <code>/</code> comme premier caractère et une ligne d'indice apparaît au-dessus de la zone de saisie, nommant le modèle qui serait joint ; tab ou un clic la complète, et quand l'emplacement cloud est fermé, la ligne se grise et dit pourquoi. votre readvisor y réfléchit alors ici d'abord — ses propres connaissances, les fichiers de ce projet, les outils wiki — détermine ce qu'il ne peut vraiment pas trancher en local, envoie <strong>une seule</strong> invite affinée, et vous répond de sa propre voix en disant quelles parties viennent du pal. un appel par message <code>/pal</code>. la même commande marche dans la zone de saisie d'un conseil, où le chef distille le brief et toute la transcription en une invite ; la réponse atterrit comme une intervention grise dont la première ligne replie ce qui a été envoyé.

### ideas
- mettez <code>:online</code> à la fin de l'id du modèle dans les réglages OpenRouter — <code>anthropic/claude-sonnet-4.5:online</code> — et votre pal répond avec le web sous les yeux. ça facture un supplément par recherche, et c'est le remède pour un modèle figé à sa date de coupure d'entraînement.
- gardez-le pour ce qu'un modèle local ne peut pas avoir : l'actualité de cette semaine, une bibliothèque sortie le mois dernier, un deuxième avis sur un jugement que vous avez déjà rendu.
- lisez la bulle sortante avant de lire la réponse. c'est le seul endroit qui montre exactement ce qui est parti, et il est là exprès.
