"""
Module de stop words français pour l'ingestor.

⚠️  Ce fichier est dupliqué dans api/src/api/stopwords.py
    Si vous modifiez ce fichier, pensez à mettre à jour l'autre aussi.
"""

# Liste complète des stop words français (version list pour l'API JSON de Meilisearch)
FRENCH_STOP_WORDS = [
    "a", "ai", "aie", "aient", "aies", "ait", "as", "au", "aura", "aurai", "auraient", "aurais", "aurait", "auras",
    "aurez", "auriez", "aurions", "aurons", "auront", "aux", "avaient", "avais", "avait", "avec", "avez", "aviez",
    "avions", "avoir", "avons", "ayant", "ayez", "ayons",
    "c", "ce", "ceci", "cela", "celle", "celles", "celui", "ces", "cet", "cette", "ceux", "chaque", "ci", "comme",
    "comment",
    "d", "dans", "de", "des", "du", "dedans", "dehors", "depuis", "deux", "devrait", "doit", "donc", "dont", "dos",
    "droite",
    "elle", "elles", "en", "encore", "es", "est", "et", "etaient", "etais", "etait", "etant", "ete", "etes", "etre",
    "eu", "eue", "eues", "eurent", "eus", "eusse", "eussent", "eusses", "eussiez", "eussions", "eut", "eux",
    "fait", "faites", "fais", "faisaient", "faisais", "faisait", "faisant", "feront", "fus", "furent", "fussent",
    "fusses", "fussiez", "fussions", "fut", "futes",
    "hors",
    "ici", "il", "ils",
    "j", "je",
    "l", "la", "le", "les", "leur", "leurs", "lui",
    "m", "ma", "maintenant", "mais", "me", "mes", "mien", "mienne", "miennes", "miens", "moi", "moins", "mon", "meme",
    "memes",
    "n", "ne", "ni", "nos", "notre", "nous",
    "on", "ont", "ou", "où",
    "par", "parce", "parmi", "pas", "peut", "peu", "plupart", "pour", "pourquoi",
    "quand", "que", "quel", "quelle", "quelles", "quels", "qui", "quoi",
    "sa", "sans", "se", "sera", "serai", "seraient", "serais", "serait", "seras", "serez", "seriez", "serions",
    "serons", "seront", "ses", "si", "sien", "sienne", "siennes", "siens", "soi", "soit", "soient", "sois", "sommes",
    "son", "sont", "soyez", "soyons", "suis", "sur",
    "t", "ta", "te", "tes", "tien", "tienne", "tiennes", "tiens", "toi", "ton", "tous", "tout", "toute", "toutes",
    "tres", "trop", "tu",
    "un", "une",
    "v", "va", "vais", "vas", "vers", "voici", "voila", "vont", "vos", "votre", "vous", "vu",
    "y"
]
