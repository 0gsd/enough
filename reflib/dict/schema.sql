CREATE TABLE forms (
    headword      TEXT NOT NULL REFERENCES words(word) ON DELETE CASCADE ON UPDATE CASCADE,
    form          TEXT NOT NULL REFERENCES words(word) ON DELETE CASCADE ON UPDATE CASCADE,
    position      INTEGER NOT NULL,      -- 1-based order within the entry's ▸ tail
    pronunciation TEXT NOT NULL,
    labels        TEXT NOT NULL,         -- JSON array, e.g. ["pl.","3rd sing."]
    synonyms      TEXT,                  -- JSON array, when the listing carries (syn. …)
    PRIMARY KEY (headword, form)
);

CREATE TABLE frequency_bands (band INTEGER PRIMARY KEY, name TEXT NOT NULL, examples TEXT);

CREATE TABLE labels (
    label    TEXT PRIMARY KEY,
    meaning  TEXT NOT NULL,
    position INTEGER NOT NULL
);

CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE synonyms (
    word     TEXT NOT NULL REFERENCES words(word) ON DELETE CASCADE ON UPDATE CASCADE,
    synonym  TEXT NOT NULL REFERENCES words(word) ON DELETE CASCADE ON UPDATE CASCADE,
    via      TEXT NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY (word, synonym, via)
);

CREATE TABLE words (
    word          TEXT PRIMARY KEY,      -- lowercase a-z
    letter        TEXT NOT NULL,         -- first letter, the A–Z section
    length        INTEGER NOT NULL,      -- characters in word
    is_headword   INTEGER NOT NULL,      -- 1 = has its own entry; 0 = exists only as a nested form of another word
    pronunciation TEXT,                  -- '/eɪ/, /ə/' when there are two; nested-only words take their first parent listing's
    ipa           TEXT,                  -- the first pronunciation alone
    definition    TEXT,                  -- plain text (headwords only)
    usage_note    TEXT,                  -- register, region, currency or field: 'Informal', 'Chiefly British', 'Now largely obsolete'
    pos           TEXT,                  -- '; '-separated, commonest first (headwords only)
    pos_primary   TEXT,                  -- the first part of speech
    synonyms      TEXT,                  -- JSON array; a headword's own list, or the union of a nested form's listings
    forms         TEXT,                  -- JSON array of {word, pronunciation, labels[], synonyms[]} in print order (headwords only)
    form_of       TEXT,                  -- the first headword this word is nested under, if any
    form_labels   TEXT,                  -- JSON array of labels from that first listing, e.g. ["pl.","3rd sing."]
    parents       TEXT,                  -- JSON array of every listing: {headword, pronunciation, labels[]}
    -- Sound. Created empty; derivable from ipa once a rhyme key is agreed.
    perfect_rhymes TEXT,                 -- JSON array of words sharing the stressed vowel and everything after it
    slant_rhymes   TEXT,                 -- JSON array of near rhymes
    homophones     TEXT,                 -- JSON array of words with the same pronunciation
    -- Proposed, created empty. Filled by later jobs.
    domain        TEXT,                  -- field: computing, food, medicine, law, …
    etymology     TEXT,                  -- origin, one short sentence
    examples      TEXT,                  -- JSON array of example sentences
    related       TEXT,                  -- JSON array of see-also words
    antonyms      TEXT,                  -- JSON array
    hyphenation   TEXT,                  -- syllable breaks for typesetting, e.g. 'aard·vark'
    frequency_rank INTEGER,              -- corpus rank, 1 = commonest
    first_use     TEXT,                  -- earliest attested year or century
    source        TEXT,                  -- provenance: 'base' or 'pack-NNN'
    added_on      TEXT,                  -- ISO date the word entered the dictionary
    updated_on    TEXT,                  -- ISO date of the last edit to this row
    status        TEXT,                  -- live, withheld, deprecated
    notes         TEXT,                  -- editorial notes (IPA oddities, sourcing questions)
    -- Per-language pairs, created empty: compare words (used our own way) and a translation of the English definition.
    fr_compare    TEXT, fr_definition TEXT,
    es_compare    TEXT, es_definition TEXT,
    de_compare    TEXT, de_definition TEXT,
    zh_compare    TEXT, zh_definition TEXT,
    ja_compare    TEXT, ja_definition TEXT
, corrected_on TEXT);

CREATE VIRTUAL TABLE words_fts USING fts5(word, definition, tokenize='unicode61 remove_diacritics 2');

CREATE INDEX forms_form ON forms(form);

CREATE INDEX synonyms_synonym ON synonyms(synonym);

CREATE INDEX words_form_of ON words(form_of);

CREATE INDEX words_ipa ON words(ipa);

CREATE INDEX words_is_headword ON words(is_headword, word);

CREATE INDEX words_letter ON words(letter);

CREATE INDEX words_pos_primary ON words(pos_primary);

CREATE VIEW entries AS
    SELECT * FROM words WHERE is_headword = 1 ORDER BY word;

CREATE VIEW sections AS
    SELECT letter, upper(letter) AS heading,
           sum(is_headword) AS headwords, count(*) AS words,
           min(word) AS first_word, max(word) AS last_word
    FROM words GROUP BY letter ORDER BY letter;

CREATE TRIGGER words_ad AFTER DELETE ON words BEGIN
    DELETE FROM words_fts WHERE word = old.word;
END;

CREATE TRIGGER words_ai AFTER INSERT ON words BEGIN
    INSERT INTO words_fts(word, definition) VALUES (new.word, new.definition);
END;

CREATE TRIGGER words_au AFTER UPDATE OF word, definition ON words BEGIN
    DELETE FROM words_fts WHERE word = old.word;
    INSERT INTO words_fts(word, definition) VALUES (new.word, new.definition);
END;
