# Audit pack specification

## Purpose

An audit pack is the buyer-facing export that turns operational evidence into a coherent proof set. It should be understandable by auditors, customers, managers, and internal reviewers without requiring direct access to the live workspace.

## Minimum contents

1. **Cover page**
   - customer or workspace name
   - pack title
   - scope period
   - export timestamp
   - pack identifier

2. **Executive summary**
   - what is being evidenced
   - why the pack was produced
   - current disposition or status

3. **Evidence register**
   - evidence ID
   - source type
   - capture timestamp
   - operator or system actor
   - hash or canonical identifier
   - relevance note

4. **Review timeline**
   - decision points
   - reviewer identity
   - policy mode used
   - approvals, quarantines, or refusals

5. **AI accountability section**
   - prompt and output references when applicable
   - model or endpoint identity
   - human review decision
   - limits or caveats

6. **Deviation or finding summary**
   - issue description
   - severity or business impact
   - corrective action or next step

7. **Export manifest**
   - file inventory
   - content hashes
   - bundle references
   - replay or verification notes

## Output expectations

The audit pack should be:

- exportable without post-processing
- readable by non-engineers
- backed by deterministic identifiers
- tied to the underlying evidence bundle
- suitable for PDF, HTML, or zipped delivery

## Recommended linked deliverables

- a human-readable audit pack document
- a machine-readable evidence manifest
- the associated evidence bundle or bundle reference
- optional screenshots or dashboards for context
