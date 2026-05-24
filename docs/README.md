# Docs Guide

This folder has a mix of active planning documents and older historical docs.
Use this file as the entry point.

If you are trying to install or run the app, do not start here. Start with the
top-level `README.md` in the repo root. This `docs/` folder is for planning and
product/design context.

## Keep and Use

These are the docs that should guide current work:

- `product-brief-template.md`
  - start here
  - fill this out yourself before making major product or system design choices
- `backend-fundamentals-4-week-roadmap.md`
  - main execution plan
  - use this for system design direction, backend learning priorities, and the
    4-week build sequence
- `v2-apartment-intelligence-spec.md`
  - product-spec reference
  - use this when you need feature-level detail for ranking, triage, source
    health, and workflow behavior

## Historical Reference Only

These are useful for background, but they should not drive current decisions:

- `spec.md`
  - original v1 watcher spec
  - mostly useful for understanding where the project started
- `apartment-intelligence-roadmap.md`
  - earlier 90-day roadmap
  - still useful for feature ideas, but superseded by the 4-week backend-focused
    roadmap

## Recommended Workflow

Use the docs in this order:

1. `product-brief-template.md`
2. `backend-fundamentals-4-week-roadmap.md`
3. `v2-apartment-intelligence-spec.md`

Recommended roles for each doc:

- `product-brief-template.md`: what are we building and for whom
- `backend-fundamentals-4-week-roadmap.md`: how do we build it in a way that
  teaches backend fundamentals
- `v2-apartment-intelligence-spec.md`: what should the product do in more detail

## What Is Not Necessary Right Now

You do not need to actively maintain all docs in parallel.

Right now, you do not need to update:

- `spec.md`, unless you want to preserve v1 history
- `apartment-intelligence-roadmap.md`, unless you want to mine it for feature
  ideas later

If we want a stricter cleanup later, the next step would be to move those two
historical docs into a `docs/archive/` folder.
