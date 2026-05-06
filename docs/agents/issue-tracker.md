# Issue tracker

Local markdown: issues are written as files under `.scratch/` in this repo.

## Format

Issues are saved as markdown files at `.scratch/<feature>/<title>.md`. Each file begins with frontmatter:

    ---
    title: <issue title>
    status: needs-triage | needs-info | ready-for-agent | ready-for-human | wontfix
    created: <ISO-8601 date>
    ---

    <description>

## Workflow

Skills that create issues: write to `.scratch/<feature>/`.
Skills that update issues: edit the `status` frontmatter field.
Skills that list issues: glob `.scratch/**/*.md` and parse frontmatter.