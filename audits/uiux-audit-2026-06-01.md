# LoreVia UI/UX Audit And Serious-Author SaaS Plan

## Evidence And Limits

Rendered browser QA could not be completed: the local Next dev server launch was rejected by the desktop approval/usage system, and the in-app Browser sandbox failed before navigation. This audit is source/static-asset based.

Static assets inspected under `frontend/public` show no obvious AI-generated raster hero art. The main visual issue is a generated-template feel: many radial gradients, glow shadows, faux dashboard mockups, and page-specific color systems.

Key source evidence:

- `frontend/src/app/page.tsx:170` and `frontend/src/app/page.tsx:285` define CSS/product mockups instead of real product proof.
- `frontend/src/app/page.tsx:501` uses layered radial gradients in the hero.
- `frontend/src/app/globals.css:347-372` defines global radial gradient shells.
- `frontend/src/components/layout/AuthorToolsNav.tsx:102` defines a large multi-section product nav.
- `frontend/src/app/(reader)/[bookId]/characters/page.tsx` has 4153 lines; `manuscript/page.tsx` has 3947 lines; `advisor/page.tsx` has 1282 lines.
- `frontend/src/components/layout/ThemeBrandImage.tsx:12-20` correctly uses real LoreVia logo assets from `frontend/public`.
- `frontend/src/components/layout/BrandLockup.tsx:8-9` declares `textClassName` and `iconClassName` but does not use them.
- `frontend/src/components/reader/ReaderToolbar.tsx:102` directly uses `/logoandtext.png` instead of the theme-aware brand helper.

## Brand And Visual Findings

- No obvious AI-generated raster illustration was found in `frontend/public`. The assets are brand marks, favicons, and `og-image.png`.
- The product still reads visually AI-generated because many pages use decorative glows, radial gradients, colorful pills, and bespoke card treatments.
- The serious-author positioning should feel editorial, private, reliable, and instrument-grade. Current design often feels like an AI demo dashboard.
- The app has too many top-level tools visible at once. The nav should sell a stable author workflow, not expose every feature as a peer.
- The real logo assets are used in the shared brand helper, which is good. Direct logo usage should be replaced with the helper so tone is correct in light/dark contexts.

## System Plan

Use one professional product language:

- Background: warm off-white in light mode, deep ink/navy in dark mode, minimal mesh only on marketing hero.
- Accent: teal for primary actions, violet only for AI/intelligence, amber only for warnings.
- Surfaces: 1px borders, subtle shadows, fewer `rounded-full` controls, no per-page glow recipes.
- Typography: editorial serif only for marketing headlines/reading; app chrome uses clean sans and tighter tables.
- Proof: replace fake dashboard mockups with real screenshots, workflow diagrams, privacy/trust proof, and sample manuscript states.
- Navigation: Library, Manuscript, Story Bible, Review Center, Collaborate, Publish/Export. Move secondary tools into tabs, command menu, or contextual side panels.

## Page-Family Plan

| Page family | Routes covered | Professional serious-author plan |
|---|---|---|
| Marketing home | `/` | Replace decorative fake product mockup with real screenshot panels: Import, Story Bible, Continuity Review, Export. Add proof bar for privacy, no-training promise, supported formats, and author outcomes. |
| Marketing education | `/blog`, `/blog/[slug]`, `/answers`, `/answers/[slug]`, `/compare`, `/compare/[slug]`, `/demo`, `/demo/[slug]` | Use a publication/editorial template: readable content width, quiet cards, no heavy gradients, clear product CTA after evidence. |
| Pricing/checkout | `/pricing`, `/upgrade`, `/checkout`, `/checkout/success` | Make plans feel transparent and serious: table comparison, limits, data/privacy note, invoice/account details. Remove glow-heavy checkout panels. |
| Auth/onboarding | `/login`, `/register`, `/forgot-password`, `/reset-password`, `/verify-email`, `/complete-username`, `/auth/callback` | Use calm centered panels with real logo, trust copy, legal acceptance clarity, and fewer decorative shadows. |
| Library/dashboard | `/library`, `/library/add-chapter`, `/stats`, `/beta-reads`, `/chats`, `/notes`, `/quotes`, `/notifications`, `/settings` | Move to a B2B app shell: list/table density, clear primary CTA, consistent empty states, account/status rail, and fewer floating/rounded controls. |
| Series workspace | `/series`, `/series/[seriesId]/ask` | Treat series as a portfolio workspace: series table, canon status, cross-book conflict queue, grounded Q&A with citations. Remove AI glow effect. |
| Book overview | `/[bookId]` | Create a project command center: current draft state, next recommended action, recent changes, risk queue, collaborator status, export readiness. |
| Manuscript/chapter/scenes | `/[bookId]/manuscript`, `/chapters`, `/chapter/[chapterId]`, `/scenes` | Editor-first layout. Keep document canvas central, move tools into right inspector, collapse low-frequency controls, standardize save/version/error states. |
| Story Bible | `/characters`, `/graph`, `/relationship-evolution`, `/timeline`, `/plot-threads`, `/summaries`, `/cross-book-wiki`, `/search` | Merge into one Story Bible hub with entity list, evidence drawer, graph/timeline tabs, source citations, and a stable details inspector. Split the huge characters page into modules. |
| Review Center | `/advisor`, `/ask`, `/analysis`, `/author-loop`, `/editorial-review`, `/foreshadowing`, `/voice`, `/world-gap`, `/reports`, `/compliance` | Consolidate AI review pages into one Review Center with queues: Continuity, Voice, Foreshadowing, World, Compliance. Use confidence, source evidence, accept/dismiss states. |
| Collaboration/beta | `/collaboration`, `/beta-feedback` | Use a professional permissions and feedback model: access matrix, reviewer timeline, unresolved comments, audit log, invitation state. |
| World building | world/canon surfaces embedded in reader | Style as a reference database: canon records, conflicts, source evidence, and accepted overrides; avoid decorative gradient cards. |
| Export/publish/public | `/export`, `/public`, `/public/[bookId]`, `/public/[bookId]/chapter/[chapterId]`, `/public/writers/[username]`, `/public/forum`, `/public/uploads`, `/public/analytics` | Separate public reader skin from author dashboard. Reading pages should be quiet, typography-first, and moderation-aware. Public uploads need trust/moderation states. |
| Legal/support/admin | `/privacy`, `/terms`, `/eula`, `/refund`, `/copyright`, `/contact`, `/status`, `/admin` | Keep a sober operations shell: tables, timestamps, policy summaries, support paths, no marketing gradients. |

## Priority Redesign Work

1. Replace global/page-specific gradient systems with a small tokenized surface system.
2. Rebuild `AuthorToolsNav` into six product areas with contextual subnav.
3. Split characters and manuscript pages into modules before visual redesign.
4. Replace homepage fake UI with screenshots or accurate product mockups.
5. Make public reader and public forum visually distinct from private author workspace.
6. Add responsive QA for library, manuscript, characters, public reader, and checkout once Browser/dev server are available.
