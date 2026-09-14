# design.md — The Lenny Growth Assistant

## 1. UI/UX principles
1. **Grounding must be visible, not just present.** Citations aren't a footnote — they're a first-class UI element (inline chips linking to source episode) so the user can verify trust at a glance rather than taking it on faith.
2. **Never let the model's silence look like a bug.** "I can't find support for that in the transcripts" is rendered as a distinct, calm UI state — not a generic error, not an empty bubble.
3. **The artifact viewer is a peer to chat, not an afterthought.** Side-by-side, not a modal or redirect — mirroring the assignment's explicit "similar to Claude Artifacts" requirement.
4. **Show the machine's configuration, don't hide it.** Which model is answering (cloud/local) is always visible — this is a config/eval tool, not a polished consumer app; transparency beats minimalism here.

## 2. Information architecture

```
┌──────────────┬─────────────────────────────┬───────────────────────┐
│  Session list │        Chat pane             │   Artifact viewer     │
│  (left rail)  │  (center, primary focus)     │   (right, collapsible)│
│               │                               │                      │
│  + New chat   │  [user/assistant turns]       │  [Markdown | HTML]    │
│  Session A    │  [citation chips]              │  tab toggle           │
│  Session B    │  [composer + provider badge]  │  rendered content     │
└──────────────┴─────────────────────────────┴───────────────────────┘
```
Three-pane layout on desktop; the artifact panel is the one element that collapses first under space pressure since chat is the primary task.

## 3. Key interaction states
| State | Treatment |
|---|---|
| Empty (no messages yet) | Short prompt suggestions ("Ask about pricing experiments," "Draft an essay on activation") rather than a blank box |
| Thinking / retrieving | Distinct "Searching transcripts…" indicator before "Generating answer…" — makes the RAG step legible instead of a generic spinner |
| Answer with citations | Answer text + citation chips below, each linking to source episode title |
| No grounding found | Calm, explicit message: "I couldn't find this in the ingested transcripts." Never silently answers from general knowledge |
| Artifact generating | Viewer panel shows a skeleton/placeholder, auto-opens when ready |
| Provider fallback triggered | Small banner: "Answered using local fallback model" — transparency over silence |
| Ollama unreachable / DB down | Inline error banner with plain-language explanation, not a raw stack trace |

## 4. Responsive behavior
- **Desktop (≥1024px):** three-pane layout as above.
- **Tablet (~768–1023px):** artifact viewer becomes a slide-over panel toggled by a button, rather than a fixed third column.
- **Mobile (<768px):** single-column; session list, chat, and artifact viewer become swipeable/tabbed views rather than simultaneous panes.

## 5. Accessibility considerations
- Assistant responses stream/append into an `aria-live="polite"` region so screen readers announce new content without interrupting typing.
- Full keyboard operability: composer, session switching, and artifact tab toggle all reachable via Tab/Enter, no mouse-only affordances.
- Color contrast meets WCAG AA for text and citation chips (not relying on color alone to signal "grounded" vs "ungrounded" — an icon + text label accompanies each).
- The artifact `<iframe>` has a descriptive `title` attribute so assistive tech announces what it is, even though its content is otherwise sandboxed.

## 6. Design decisions worth noting
- No dark/light theme toggle in v1 — one well-considered theme beats two half-considered ones under this time budget (documented non-goal, not an oversight).
- Citation chips show the episode title, not a raw chunk ID — the evaluator shouldn't need to understand the retrieval internals to trust the answer.
