# Constitution Update Checklist

When amending the constitution (`/memory/constitution.md`), ensure all dependent documents are updated to maintain consistency.

## Templates to Update

### When adding/modifying ANY article:
- [x] `/templates/plan-template.md` - Update Constitution Check section
- [x] `/templates/spec-template.md` - Update if requirements/scope affected
- [x] `/templates/tasks-template.md` - Update if new task types needed
- [ ] `/CLAUDE.md` - Update runtime development guidelines (file does not exist yet)

### Article-specific updates:

#### Article I (Do No Harm):
- [x] Ensure templates require validity verification steps
- [x] Update test requirements to include bids-examples sweeps
- [x] Add dry-run requirements to CLI command templates

#### Article II (Schema-Driven):
- [x] Update dependency references in templates
- [x] Ensure schema version compatibility is documented

#### Article III (Library-First):
- [x] Ensure templates emphasize library API before CLI
- [x] Update import/module structure guidance

#### Article IV (CLI Excellence):
- [x] Update CLI flag requirements in templates
- [x] Add dry-run and verbosity requirements

#### Article V (Test-First):
- [x] Update test order in all templates
- [x] Emphasize TDD requirements and bids-examples usage
- [x] Add test approval gates

#### Article VI (Performance at Scale):
- [x] Add performance considerations to plan template
- [x] Include profiling steps in task template

#### Article VII (VCS Awareness):
- [x] Add VCS detection requirements to implementation templates
- [x] Include git-annex/DataLad considerations

#### Article VIII (Observability):
- [x] Add logging requirements to templates
- [x] Include change manifest output specifications

#### Article IX (Simplicity):
- [x] Update YAGNI reminders in templates
- [x] Add complexity justification requirements

#### Article X (Versioning & Breaking Changes):
- [x] SemVer policy documented in constitution
- [x] Migration guide and deprecation requirements specified

#### Article XI (DRY — No Code Duplication):
- [x] Duplication detection tooling specified (pylint + jscpd)
- [x] Enforcement via tox testenvs documented
- [x] Allowed exceptions with rationale requirements listed

## Validation Steps

1. **Before committing constitution changes:**
   - [x] All templates reference new requirements
   - [x] Examples updated to match new rules
   - [x] No contradictions between documents

2. **After updating templates:**
   - [ ] Run through a sample implementation plan (pending — no specs written yet)
   - [x] Verify all constitution requirements addressed
   - [x] Check that templates are self-contained

3. **Version tracking:**
   - [x] Update constitution version number
   - [x] Note version in template footers
   - [x] Add amendment to constitution history

## Template Sync Status

Last sync check: 2026-04-02
- Constitution version: 1.4.0
- Templates aligned: Yes (plan, spec, tasks, checklist templates all present)
- Pending: `/CLAUDE.md` (root project guidance file not yet created)

---

*This checklist ensures the constitution's principles are consistently applied across all project documentation.*
