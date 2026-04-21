# Default Paradigm

This is the base interaction paradigm. It defines how sessions work.

## Session Structure
- Single agent, conversational mode
- No specific phase structure — freeform interaction

## Output Conventions
- Respond in plain text unless the user requests a specific format
- When creating files, explain what you're creating and why before doing it
- When using shell commands, show the command before executing it

## Archival Policy
- All exchanges are logged to session-logs/
- MOTIVATION.md updates are proposed at session end, not applied automatically

## Security Posture
- Tool use is unrestricted within the project directory.
- Network access is gated per skill (e.g. the-internet uses Tor).
- Reading files outside the project directory is allowed if explicitly
  asked, as is finding a local file and making a copy into the project
  directory.
- Do not move files out of or into the project directory yourself.
- Do not write files outside the project directory.
- In general, do not delete files (including within the project directory)
  unless explicitly asked and confirmed by the user.
