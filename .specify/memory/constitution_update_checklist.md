# Constitution Update Checklist

When amending the constitution (`/memory/constitution.md`), ensure all dependent documents are updated to maintain consistency.

## Templates to Update

### When adding/modifying ANY article:
- [ ] `/templates/plan-template.md` - Update Constitution Check section
- [ ] `/templates/spec-template.md` - Update if requirements/scope affected
- [ ] `/templates/tasks-template.md` - Update if new task types needed
- [ ] `/.claude/commands/plan.md` - Update if planning process changes
- [ ] `/.claude/commands/tasks.md` - Update if task generation affected
- [ ] `/CLAUDE.md` - Update runtime development guidelines

### Article-specific updates:

#### Article I (Do No Harm):
- [ ] Ensure templates require validity verification steps
- [ ] Update test requirements to include bids-examples sweeps
- [ ] Add dry-run requirements to CLI command templates

#### Article II (Schema-Driven):
- [ ] Update dependency references in templates
- [ ] Ensure schema version compatibility is documented

#### Article III (Library-First):
- [ ] Ensure templates emphasize library API before CLI
- [ ] Update import/module structure guidance

#### Article IV (CLI Excellence):
- [ ] Update CLI flag requirements in templates
- [ ] Add dry-run and verbosity requirements

#### Article V (Test-First):
- [ ] Update test order in all templates
- [ ] Emphasize TDD requirements and bids-examples usage
- [ ] Add test approval gates

#### Article VI (Performance at Scale):
- [ ] Add performance considerations to plan template
- [ ] Include profiling steps in task template

#### Article VII (VCS Awareness):
- [ ] Add VCS detection requirements to implementation templates
- [ ] Include git-annex/DataLad considerations

#### Article VIII (Observability):
- [ ] Add logging requirements to templates
- [ ] Include change manifest output specifications

#### Article IX (Simplicity):
- [ ] Update YAGNI reminders in templates
- [ ] Add complexity justification requirements

## Validation Steps

1. **Before committing constitution changes:**
   - [ ] All templates reference new requirements
   - [ ] Examples updated to match new rules
   - [ ] No contradictions between documents

2. **After updating templates:**
   - [ ] Run through a sample implementation plan
   - [ ] Verify all constitution requirements addressed
   - [ ] Check that templates are self-contained

3. **Version tracking:**
   - [ ] Update constitution version number
   - [ ] Note version in template footers
   - [ ] Add amendment to constitution history

## Template Sync Status

Last sync check: 2026-03-21
- Constitution version: 1.0.0
- Templates aligned: N/A (initial creation, templates pending)

---

*This checklist ensures the constitution's principles are consistently applied across all project documentation.*
