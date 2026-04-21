# Anonymity model

## What Tor gives you

Tor routes each connection through three relays:

    you → guard → middle → exit → destination

The destination site sees only the exit node's IP. Your ISP sees only that
you're talking to the guard (an entry to the Tor network), not what's
inside the tunnel. No single relay in the chain knows both who you are
*and* what you're fetching.

## What stream isolation adds

By default, every invocation of a script in this skill assigns a random
SOCKS5 username/password pair. Tor interprets different (user, pass)
tuples as different streams and pushes each onto its own circuit with its
own exit node. Practical consequence:

    Request A → exit node in Germany
    Request B → exit node in Romania
    Request C → exit node in Brazil

The three destination sites have no shared network-layer signal to
conclude that these requests came from the same source.

Compare with naive curl-over-Tor: all your requests share one circuit
until Tor rotates it (roughly every 10 minutes), so sites can trivially
link everything you fetched in that window by exit IP.

When you explicitly pass `--isolation-id <same-string>`, you opt *out* of
fresh isolation and reuse the same circuit — useful for paginating one
site or fetching linked documents from one source, where behaving like
one coherent user is less anomalous than behaving like fifty unrelated
ones.

## What it protects

- **Network-layer identity.** Your real IP never reaches the destination.
- **Request linkability by IP.** Two sites cannot compare logs and
  conclude that the same client hit both of them.
- **Passive ISP surveillance of content.** Your ISP sees encrypted Tor
  traffic, not URLs or payloads.
- **Geolocation targeting.** Sites can't geoblock you based on your
  actual country; they see the exit node's country, which varies per
  request by default.

## What it does NOT protect

### Semantic correlation

Fetching 50 articles on the same niche topic in the same hour produces a
signal no transport-layer tool can hide. If your research is topically
narrow and the adversary has wide visibility (e.g., they own the sites
you're querying, or buy data from them), topic-based fingerprinting
still works. Tor fixes the pipe, not the contents.

### Accounts and cookies

Log in once, and you've linked the circuit to your identity for the rest
of that session. Log in with the same account across two circuits, and
you've given the site a way to correlate those circuits yourself. **This
skill is not for logged-in browsing.** Don't do it.

### Browser fingerprinting

This skill doesn't run a real browser, so canvas / WebGL / audio context
fingerprinting isn't a concern — but we *do* send a User-Agent string.
The skill randomizes from a small pool of common values; this is
strictly better than sending a unique UA (which would be a fingerprint
in itself) and strictly worse than masquerading as Tor Browser exactly.
If you need rigorous browser-level anonymity, use Tor Browser, not this
skill.

Header order and TLS fingerprints (JA3/JA4) are also not spoofed. The
`requests` library has its own TLS fingerprint, which is identifiable
as "Python requests" if anyone's looking. For most research use cases
this doesn't matter; for adversarial research against a
fingerprint-savvy target, it does.

### Timing correlation

A global passive adversary observing both the guard node and the
destination can correlate traffic by packet timing. This is Tor's
known, long-documented weakness, and no wrapper around it fixes it.

### Exit-node tampering

Malicious exit nodes can read and inject plaintext HTTP. The skill
speaks HTTPS to all real sites and does not disable certificate
verification — so TLS terminates at the destination, not the exit, and
the exit sees only encrypted bytes. **Do not disable TLS verification
in custom modifications.** If you fetch an HTTP (non-S) URL, the exit
node can and sometimes does modify the response.

### Your own mistakes

- Pasting an API key or auth token into a request
- Fetching a URL that encodes your email or user ID in query parameters
- Fetching a URL that came to you via an email tracking link
- Running this on a machine that also has identifying cookies / sessions
  leaking through other processes (it doesn't — this is a separate
  Python process — but don't, say, screenshot the output and upload it
  somewhere identifying)

---

## Threat models this skill fits

- Journalist researching a story without tipping off subjects
- Lawyer researching opposing counsel without generating an attributable
  log
- Person researching a medical condition without it chasing them around
  the ad network for three months
- Developer auditing their own site's behavior from an outside vantage
- Researcher reading primary sources (dissident media, foreign
  government docs, academic preprints) without building an institutional
  profile
- Anyone reading open text (Gutenberg, RFCs, manifestos, public
  records) for the simple reason that their reading habits are nobody's
  business

## Threat models this skill does NOT fit

- Evading a nation-state adversary with global passive traffic analysis.
  Use Tor Browser at minimum, probably something more specialized, and
  reconsider your operational security end-to-end.
- Anonymously doing anything illegal. Tor is not invisibility. Legal
  exposure does not evaporate because you used a SOCKS proxy, and the
  skill's refusal rules apply regardless. See `ethical-use.md`.
