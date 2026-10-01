# Validation records

Each folder records one change as it was made: what changed, the commands and
suites that checked it, their results, and what was not verified. The docs
link to these records as evidence.

These records predate Kestrel 128's public repository. They were written
during its development under the earlier name uOS 128, and the commit
hashes, file names and scratch paths they cite refer to that private
development history, not to this repository's commits.

Only each record's README and its small top-level reports (Markdown and JSON)
are published. The full records also held the frozen inputs of each run
(copies of the test harness and disk images), raw logs and captured screens,
about 1.3 GB in all; links inside a record to those files do not resolve here.

Before publication, personal details were replaced throughout these records
and the build listings: home-directory paths by `<home>` (temporary build
folders by `<tmp>`), local network addresses by the documentation range
`192.0.2.x` with the last number kept, and the agent's email address by
`<agent>`. Nothing else was changed, but checksums recorded in a record no
longer match the files those replacements touched.
