# Initial design ideas

Based on the content of the issue https://github.com/bids-standard/bids-utils/issues/2

For a while I felt the need, and at some point expressed it (but forgot where), to get a command line (or may be eventually some GUI) utility to manipulate a BIDS dataset.  Quite often due to inherent redundancy, some trivial operations are not that trivial. E.g.

note: the list has being edited (last in March 2026) to reflect discovered needs

## List of commands/needs with priorities

- **migrate** (need: high):  establish migration path(s) to address deprecations and potential breaking changes for BIDS 2.0
  - prototype: based on https://github.com/bids-standard/bids-specification/pull/1775, copilot extracted into https://github.com/bids-standard/bids-specification/pull/2282 within `bst`
- **renaming a subject** (need: medium): (codename `subject-rename` for now) requires
  - renaming `sub-` directory
    - possibly also under `sourcedata/` (and who knows -- may be `.heudiconv/`)
  - renaming every file under that directory since they all carry `sub-` prefix
    - possibly also under `sourcedata/`
  - fixing up `_scans` file as well since that is where those files are listed as well
  - modifying `participants.json`
- **remove a subject[/session]** (need: low)
- **remove a run** (need: low) while shifting all subsequent run indexes
- **rename or fix a filename** (need: high) (just `rename`) - could be used by `subject-rename` -- since a file might have a side car file, and then listed in `_scans`, might come handy
   - some non-BIDS compliant file, e.g. having spurious suffix like a `_test`
   - prototypes:
     - spacetop dataset (openneuro ds005256, [rename_file](https://github.com/spatialtopology/ds005256/blob/master/code/rename_file))
   - related efforts inspired by working on BIDS datasets:
     - [rename-tool](https://github.com/just-meng/rename-tool) by @just-meng
- **renaming a session** (need: medium) (`session-rename`)
- **moving into a session** (need: medium) (`session-rename '' session`) -- whenever dataset (or a specific subject?) was collected without any session'ing, and then multiple sessions decided to be taken
- **merge datasets** (need: low) - implementation might relate to *Moving into a session*. Take two datasets (possibly without sessions) and then merge them either by
- **split datasets** (need: low) - the opposite of merging -- some times it is useful to generate a dataset which contains e.g. only behavioral data, or only stimuli, to facilitate more efficient sharing and reuse

   - just combining subjects (and failing if conflicting)
   - placing each one into a (specified) session
   - using subjects (re)mapping file
- **bubble-up/condense/organize metadata** (need: medium) - move common (meta)data up in the hierarchy to make BIDS dataset easier for users to find at higher level, and not duplicated underneath (
   - [inheritance principle](https://bids-specification.readthedocs.io/en/stable/common-principles.html#the-inheritance-principle), [bids, 1.10.2 (IIRC), 2: summarization](https://github.com/bids-standard/bids-2-devel/issues/65))
     - prototype: @Lestropie initiated https://github.com/Lestropie/IP-freely (TODO: review)
     - could have modes to
        - `aggregate` -- propagate up common metadata (so easy to overview what is common)
        - `segregate` -- propagate down into the leafs (so easy to view/share individual subj/sess with all metadata)
        - `deduplicate` -- combined with either of the above to remove either at the leafs or at the roots, leaving only a single source (among .tsv/.json etc; might still be within .nwb etc if was extracted from there)
     - notes:  for 'aggregate' we need to be careful to not state a common metadata attribute at higher level if it was missing entirely from some involved file or missing such file entirely! e.g. if all subjects have consistent `RepetitionTime` in their `_bold.json` but then one subject lacks `_bold.json` entirely for its `_bold.nii.gz` ! Also here we could have different "modes" of aggregation as there could be aggressive aggregation into top level
           - `bold.json` - common across all bolds
          - `task-rest_bold.json` - specific to `task-rest`
          - `task-motor_bold.json` - specific to `task-motor`
          - `acq-et41_bold.json` - specific to `acq-et41`
       vs  e.g.
          - `task-rest_bold.json`
          - `task-rest_acq-et41_bold.json`
          - `task-motor_bold.json`
          - `task-motor_acq-et41_bold.json`
    - "audit": Identify metadata values that are neither unique across metadata files nor equivalent across metadata files, but somewhere in between; this precludes exploitation of inheritance principle, and can be indicative of some error in acquisition harmonisation.

## Various related ideas

### Testing

- we have outstanding and well maintained https://github.com/bids-standard/bids-examples/ of valid datasets of different kinds.  We must make as much use of it as possible, e.g.
  - for each command sweep through datasets, perform basic operation(s) they implement while verifying that valid (before) datasets remain valid after the operation!
  - commands could be applied 'randomly' , as e.g. for `rename-subject` take a random subject folder and rename randomly. That could potentially be beneficial to increase coverage over use-cases since not necessarily all subjects are totally uniform

### Extra features

-  **git/git-annex awareness** (need: medium):
   - Ideally the tool should be aware of git and/or git-annex, i.e. that files might be under VCS and then should use corresponding VCS functions.
   - If for the function we need content of the files it could either be obtained (`datalad get`) or accessed transparently remotely (through fsspec + info from annex. See https://github.com/datalad/datalad-fuse/ providing support interfaces

## Development 'plan'

### Template

I would like to use one of the copier templates to initiate this project. Side-goals for that would be to learn to use copier more to maintain scaffolding, benefit from best practices established already by those templates. Here are candidate templates from https://github.com/topics/copier-template which I am considering in order of preference somewhat

- https://github.com/ritwiktiwari/copier-astral - seems minimal, uv oriented
- https://github.com/NLeSC/python-template - comes from sciency folks, integration with zenodo etc
- https://github.com/superlinear-ai/substrate 

Some 'wishes' which might not be fulfilled by above but stating for review

- to stay with `tox` to centralize tooling and testing.
- do use uv, and tox-uv if using tox
- to be inline with what we use elsewhere in bids-specification project (e.g. mkdocs for docs)

### "Spec-driven" AI assist

I, and various others, had good experience developing using https://github.com/github/spec-kit with `claude code`.  So I think I will approach this project with `spec-kit`, feeding it this document for guidance across various stages.

## Other related thoughts

Originally I thought to propose this development within pybids, but per-se such utility (`bids`) does not have to (although likely will) be implemented using pybids. Some functionalities, which operate on BIDS-compliant datasets, could be achieved via re-layouting using pybids, but then it should also become capable to capture those under `.heudiconv` and `sourcedata/` which is not strongly "prescribed" in BIDS (there is only a recommendation to follow BIDS naming there as well)
