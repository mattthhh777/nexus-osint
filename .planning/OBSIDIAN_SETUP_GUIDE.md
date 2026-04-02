# Obsidian Second Brain Setup Guide
**NexusOSINT v4.0 Development Environment**

---

## Overview

Obsidian serves as your persistent memory system for:
- Project documentation and decisions
- Technical research and findings
- Session notes and context
- Decision trees and architecture diagrams
- Integration with claude-mem for cross-session learning

This guide configures Obsidian to work seamlessly with Claude Code and GSD workflows.

---

## 1. Creating the Obsidian Vault

### Step 1: Create Vault Directory
```bash
# Create base directory
mkdir -p "~/Obsidian Vaults/NexusOSINT"

# Create subdirectories
mkdir -p "~/Obsidian Vaults/NexusOSINT/daily"
mkdir -p "~/Obsidian Vaults/NexusOSINT/memory"
mkdir -p "~/Obsidian Vaults/NexusOSINT/projects"
mkdir -p "~/Obsidian Vaults/NexusOSINT/research"
mkdir -p "~/Obsidian Vaults/NexusOSINT/decisions"
mkdir -p "~/Obsidian Vaults/NexusOSINT/_quick-capture"
mkdir -p "~/Obsidian Vaults/NexusOSINT/.attachments"
```

### Step 2: Initialize Obsidian Vault
1. Open **Obsidian** desktop app
2. Click **"Open vault folder"**
3. Navigate to `~/Obsidian Vaults/NexusOSINT`
4. Click **"Open"**

Obsidian will automatically create `.obsidian/` config folder.

---

## 2. Vault Structure

```
NexusOSINT/
├── daily/                      # Daily standup notes
│   ├── 2026-03-30.md
│   └── 2026-03-31.md
├── memory/                     # Cross-session memory
│   ├── decisions.md            # Architectural decisions
│   ├── patterns.md             # Code patterns & templates
│   ├── blockers.md             # Known issues
│   └── glossary.md             # Project terminology
├── projects/                   # Project-specific notes
│   ├── v4.0-roadmap.md         # Milestone roadmap
│   ├── f1-audit.md             # Feature 1 notes
│   └── ...
├── research/                   # Technical research
│   ├── async-agents.md
│   ├── sqlite-optimization.md
│   └── ...
├── decisions/                  # ADRs (Architecture Decision Records)
│   ├── adr-001-async-agents.md
│   └── adr-002-memory-arch.md
├── _quick-capture/             # Temporary notes (auto-created)
├── .attachments/               # Images and attachments
├── .obsidian/                  # Obsidian config (auto-created)
├── README.md                   # Vault overview
└── INDEX.md                    # Navigation index
```

---

## 3. Initial Files to Create

### INDEX.md (Navigation Hub)
```markdown
# NexusOSINT Development Hub

## Quick Access
- [[daily/2026-03-30|Today's Notes]]
- [[projects/v4.0-roadmap|v4.0 Roadmap]]
- [[memory/decisions|Architecture Decisions]]

## Features (v4.0)
- [[projects/f1-audit|F1: Codebase Audit]]
- [[projects/f2-sqlite|F2: SQLite Hardening]]
- [[projects/f3-agents|F3: Async Agents]]

## Memory
- [[memory/patterns|Code Patterns]]
- [[memory/blockers|Known Issues]]
- [[research/async-agents|Research Notes]]

## Recent Decisions
- [[decisions/adr-001|ADR-001: Async Agent Architecture]]
```

### daily/TEMPLATE.md (Daily Template)
```markdown
# Daily Standup - {{DATE}}

## Yesterday
- [ ] Task 1
- [ ] Task 2

## Today
- [ ] Task 1
- [ ] Task 2

## Blockers
- None

## Notes
-

## Links
- [[../memory/decisions]]
- [[../projects/v4.0-roadmap]]
```

### memory/decisions.md (Architecture Decisions)
```markdown
# Architecture Decisions

## ADR-001: Async Agent Orchestration
**Date**: 2026-03-30
**Status**: ACTIVE

### Decision
Use `asyncio.TaskGroup` + `Semaphore(5)` for agent orchestration

### Rationale
- TaskGroup ensures no orphaned tasks
- Semaphore prevents resource exhaustion
- Python 3.11+ native support

### Related
- [[../decisions/adr-001]]
- [[../research/async-agents]]
```

---

## 4. Integration with Claude Code

### Hook Configuration
The SessionStart hook automatically:
1. ✅ Validates all 44+ skills
2. ✅ Checks Obsidian vault exists
3. ✅ Displays readiness summary

### Using Obsidian Skills in Claude Code

After vault is set up, use these commands:

#### Create Daily Note
```
/obsidian-markdown create daily note for today
```

#### Capture Quick Note
```
/obsidian-markdown add to quick-capture: "Found memory leak in agent loop"
```

#### Link Decision
```
/obsidian-markdown update INDEX.md with new ADR
```

---

## 5. Obsidian Plugins (Optional but Recommended)

Install via **Obsidian Settings > Community Plugins**:

| Plugin | Purpose | Status |
|--------|---------|--------|
| **Daily Notes** | Auto-creates dated notes | Core feature |
| **Templates** | Reuse note templates | Recommended |
| **Dataview** | Query notes like database | Recommended |
| **Canvas** | Visual note connections | Optional |
| **Excalidraw** | Embedded diagrams | Optional |
| **Git** | Version control notes | Recommended |

---

## 6. Connecting to GSD Workflow

### Before Starting a Phase
```bash
# 1. Open Obsidian vault (separate window)
# 2. Update daily standup
# 3. Link to relevant ADRs/decisions
# 4. In Claude Code: /gsd:resume-work

The hook will load Obsidian context automatically
```

### During Phase Execution
```bash
# Use claude-mem skills to capture findings
/claude-mem:mem-search "async agents"

# Update Obsidian in parallel
/obsidian-markdown update projects/v4.0-roadmap

# Link decisions
/obsidian-markdown create ADR for this decision
```

### After Phase Completion
```bash
# Document learnings
/obsidian-markdown add to memory/patterns

# Update decisions log
/obsidian-markdown update decisions with completed ADRs

# Create summary
/obsidian-markdown create project summary
```

---

## 7. Linking Obsidian to claude-mem

### Export for Memory
When you want to save Obsidian notes to claude-mem:

```bash
# Use obsidian-cli to export
/obsidian:obsidian-cli export memory/

# Then save to claude-mem
/claude-mem:mem-search results
```

### Two-Brain System
```
┌─────────────────────────────────────────┐
│ Session (Claude Code + Skills)          │
│ • Active work                           │
│ • Real-time decisions                   │
└─────────────────────────────────────────┘
           ↓ /obsidian-markdown
┌─────────────────────────────────────────┐
│ Obsidian Vault (Long-term Memory)       │
│ • Architecture decisions (ADRs)         │
│ • Patterns & templates                  │
│ • Research & findings                   │
└─────────────────────────────────────────┘
           ↓ /claude-mem integration
┌─────────────────────────────────────────┐
│ claude-mem (Cross-Session Memory)       │
│ • Project context (1000+ entries)       │
│ • Decision history                      │
│ • Learned patterns                      │
└─────────────────────────────────────────┘
```

---

## 8. Quick Start Checklist

- [ ] Create vault directory: `~/Obsidian Vaults/NexusOSINT`
- [ ] Open in Obsidian desktop app
- [ ] Create subdirectories (daily, memory, projects, etc)
- [ ] Create INDEX.md
- [ ] Create daily/TEMPLATE.md
- [ ] Create memory/decisions.md
- [ ] Create projects/v4.0-roadmap.md
- [ ] Install optional plugins
- [ ] Test `/gsd:resume-work` (should show Obsidian status)
- [ ] Create first daily note
- [ ] Link first ADR in decisions

---

## 9. Troubleshooting

### Hook not detecting Obsidian vault?
```bash
# Check path in hook:
# C:/Users/vtbit/.claude/hooks/obsidian-context-loader.js

# Should look for:
# ~/Obsidian Vaults/NexusOSINT

# Verify location:
ls ~/Obsidian\ Vaults/NexusOSINT/.obsidian
```

### Notes not showing up in daily?
```bash
# Make sure note is in correct format:
# daily/YYYY-MM-DD.md

# Example:
# daily/2026-03-30.md
```

### Obsidian plugins not working?
- Go to **Settings > Community Plugins > Reload**
- Check plugin is enabled (toggle switch ON)
- Restart Obsidian app

---

## 10. Next Steps

After vault is set up:

1. **Run GSD workflow**
   ```bash
   /gsd:resume-work
   ```
   Should show:
   ```
   ✅ Obsidian Second Brain Status:
      ✅ Vault root: OK
      ✅ Config: OK
      ✅ Quick Capture: OK
   ```

2. **Create first ADR**
   ```bash
   /obsidian-markdown create "ADR-001: Architecture Decision"
   ```

3. **Link to v4.0 roadmap**
   Update `projects/v4.0-roadmap.md` with feature links

4. **Start daily standups**
   Create `daily/2026-03-30.md` each morning

---

## 11. Integration with NexusOSINT Project

Add to project `.gitignore`:
```gitignore
# Obsidian local config
Obsidian Vaults/
!Obsidian Vaults/NexusOSINT/
Obsidian Vaults/NexusOSINT/.obsidian/
```

Document in project CLAUDE.md:
```markdown
## Second Brain (Obsidian)

Location: `~/Obsidian Vaults/NexusOSINT/`

Before starting work:
1. Open Obsidian vault
2. Check daily notes
3. Review open ADRs in `decisions/`
4. Run `/gsd:resume-work`

Hook will validate vault status automatically.
```

---

## References

- **Obsidian**: https://obsidian.md/
- **Obsidian Help**: https://help.obsidian.md/
- **ADR Template**: https://adr.github.io/
- **Claude Obsidian Skills**: `/obsidian-markdown`, `/obsidian-cli`

---

**Status**: ✅ Ready to use
**Last Updated**: 2026-03-30
