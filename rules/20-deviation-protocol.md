## Rule: deviation protocol

You can break a convention only with a Convention Deviation Record (CDR). Use the CDR template from the skill `magenta-templates`. Save it in `.magenta/work/<ID>/decisions/`.

The CDR states:

1. The convention, with a file reference.
2. The problem that the convention causes in this case, with evidence.
3. The alternative and its blast radius: files, modules, teams, and migration.
4. The scope: this change only, or a new convention for all new code.

Approval:

- Local deviation: the Principal approves it in a decision note.
- New convention: the Architect writes an ADR. The human approves it.

Silent deviations are not permitted. Mixed styles without a migration plan are not permitted.
