# Requirements: NexusOSINT Refactoring Milestone

**Defined:** 2026-03-25
**Core Value:** A single search query returns comprehensive intelligence from 13+ OSINT modules with professional-grade data presentation — density without chaos.

## v1 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### CSS Token Migration (Meridian Design System)

- [x] **CSS-01**: All 9 CSS files use Meridian semantic tokens instead of legacy tokens (--bg, --text, --amber, --line, etc.)
- [x] **CSS-02**: Zero hardcoded rgba() color values in CSS files — all replaced by token references (--color-accent-muted, --color-border-subtle, etc.)
- [x] **CSS-03**: All border-radius values constrained to design system scale: 2px (badges), 4px (buttons/inputs), 6px (cards/panels), 999px (category chips only)
- [x] **CSS-04**: All spacing values use --space-* tokens instead of arbitrary px values (14px, 18px, 36px, 56px, 68px)
- [x] **CSS-05**: All font-size values use --text-* tokens instead of hardcoded px/rem values
- [x] **CSS-06**: All font-family declarations use --font-display, --font-data, or --font-body tokens
- [x] **CSS-07**: All box-shadow values use --shadow-* tokens
- [x] **CSS-08**: All transition durations use --duration-* and --ease-* tokens
- [x] **CSS-09**: All z-index values use --z-* tokens
- [x] **CSS-10**: tokens.css contains the complete Meridian design system as single :root declaration
- [ ] **CSS-11**: Visual output is identical to pre-migration (zero visual regression)
- [x] **CSS-12**: Changing --color-accent to a different color causes ALL accent elements to update (token propagation verified)

### XSS Sanitization

- [ ] **XSS-01**: sanitizeImageUrl() function validates all URLs before insertion into src= or background-image (reject non-https, reject javascript: protocol)
- [ ] **XSS-02**: Discord avatar and banner URLs from OathNet API pass through sanitizeImageUrl() before DOM insertion
- [ ] **XSS-03**: esc() function applied to ALL template literal interpolations in render.js where API data is inserted into HTML
- [ ] **XSS-04**: grep confirms zero instances of unescaped API data in template literals across all JS files

## v2 Requirements

Deferred to future milestone. Tracked but not in current roadmap.

### Security Hardening

- **SEC-01**: JWT migrated from localStorage to httpOnly cookies
- **SEC-02**: Admin HTML endpoint requires server-side auth check before serving
- **SEC-03**: OathnetClient uses singleton pattern instead of per-request instantiation

### Feature Additions

- **FEAT-01**: report_generator.py integrated into main.py with /api/report/generate endpoint
- **FEAT-02**: Cases and history persisted server-side in SQLite
- **FEAT-03**: Per-user credit system for OathNet quota management
- **FEAT-04**: Sherlock expanded from 25 to 60+ platforms

### Quality

- **QUAL-01**: pytest test suite covering auth, rate limiting, and input sanitization
- **QUAL-02**: Frontend unit tests for utils.js pure functions

## Out of Scope

| Feature | Reason |
|---------|--------|
| Next.js / React migration | Production stack works, rewrite risk too high for refactoring milestone |
| n8n integration | Never existed, not needed for current work |
| PostgreSQL / Redis | SQLite sufficient at current scale |
| Tailwind CSS / Shadcn/ui | Using custom Meridian design system |
| New OSINT modules | Feature work, not refactoring |
| Backend refactoring (split main.py) | Separate initiative, not blocking current work |
| OathNet client async migration | Works fine via asyncio.to_thread |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CSS-01 | Phase 1 | Complete |
| CSS-02 | Phase 1 | Complete |
| CSS-03 | Phase 1 | Complete |
| CSS-04 | Phase 1 | Complete |
| CSS-05 | Phase 1 | Complete |
| CSS-06 | Phase 1 | Complete |
| CSS-07 | Phase 1 | Complete |
| CSS-08 | Phase 1 | Complete |
| CSS-09 | Phase 1 | Complete |
| CSS-10 | Phase 1 | Complete |
| CSS-11 | Phase 1 | Pending |
| CSS-12 | Phase 1 | Complete |
| XSS-01 | Phase 2 | Pending |
| XSS-02 | Phase 2 | Pending |
| XSS-03 | Phase 2 | Pending |
| XSS-04 | Phase 2 | Pending |

**Coverage:**
- v1 requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0

---
*Requirements defined: 2026-03-25*
*Last updated: 2026-03-25 after roadmap creation*
