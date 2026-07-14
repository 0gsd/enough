# Mermaid syntax reference (vendored)

On-demand syntax documentation for the diagram types the
`girraph-merirmaid` skill generates into `.merirmaid` files. Read the
page for the diagram type you are about to write; don't reproduce a
diagram type from memory when the exact syntax is one `read_file` away.

These files are excerpted from the official Mermaid documentation
(<https://mermaid.js.org>, source repo
<https://github.com/mermaid-js/mermaid>), which is MIT licensed. Only
the syntax-documentation body is kept; the site's Jekyll frontmatter
and navigation boilerplate were stripped. Each file keeps a one-line
attribution header pointing at its upstream source. The vendored
renderer these diagrams target is `enough/static/mermaid.min.js`
(Mermaid v11).

| File | Diagram type | Use it for |
|---|---|---|
| [flowchart.md](flowchart.md) | `flowchart` / `graph` | Structures, decision flows, dependency maps — the default choice. |
| [sequence.md](sequence.md) | `sequenceDiagram` | Interactions/message-passing between actors over time. |
| [class.md](class.md) | `classDiagram` | Type/data models, object relationships, schemas as classes. |
| [state.md](state.md) | `stateDiagram-v2` | Lifecycles, state machines, mode transitions. |
| [entity-relationship.md](entity-relationship.md) | `erDiagram` | Database/domain entities and their relationships. |
| [gantt.md](gantt.md) | `gantt` | Schedules, timelines, project plans with dates. |
| [pie.md](pie.md) | `pie` | Simple proportion/share breakdowns. |
| [mindmap.md](mindmap.md) | `mindmap` | Loose hierarchical brainstorms radiating from one center. |

Reach for a **flowchart** unless the request clearly matches one of the
others; it is the format users read most fluently and edit most easily.

For choosing between a `.merirmaid` and a `.girraph` in the first place,
and for the `.merirmaid` frontmatter/modality rules, see the parent
`SKILL.md` — not these files.
