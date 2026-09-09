# Project map review

Map resolution is implemented in `app/core/project_maps.py`. The canonical
notice text and geography are unchanged. Public routes compute map actions at
read time, so no notice-data rewrite is required.

## Rules

- Use title location tokens only. General bodies and excerpts often name receipt
  offices rather than the project. Body-only locations are withheld until an
  explicitly evidenced project-location field is available.
- Prefer named roads over redundant route numbers. Google treated CR-601 as a
  house number in the Spring Valley test.
- Preserve explicit intersection pairs; do not manufacture intersections from
  lists of independent roads. Separate multiple roads/routes into separate links.
- Multiple county names do not establish which route belongs to which county.
- Ordinary links are searches, not verified pins or contract limits.
- A verified structure requires an official identity reference and a reviewed
  map destination. Every registry entry must have a review date and official
  evidence URL. Match all identifying conditions, not just a name or route.
- Research assistants may propose entries but cannot publish unreviewed matches.
  Include a positive fixture and wrong-direction/wrong-crossing negative fixtures.

## Browser observations, 2026-09-09

These are a small manual sample, not a general success-rate estimate.

| Query | Observed result |
|---|---|
| Full Spring Valley resurfacing title | Construction company in Somerville |
| Spring Valley Road, CR-601, Morris County, New Jersey | 601 Spring Valley Road building |
| Spring Valley Road, Morris County, New Jersey | Spring Valley Road near Loantaka Brook; road context, not limits |
| Full Marlboro intersection engineering title | Engineering company in Manalapan |
| Tennent Road & Spring Valley Road, Marlboro, New Jersey | Named intersection in Marlboro |
| Bailey's Mill Road bridge over Interstate 287, Morris County, New Jersey | 287 Baileys Mill Road; not a verified crossing |
| Rt 1 NB, Bridge over Raritan River | Multiple bridges; railroad bridge first |
| Morris Goodkind Bridge, New Jersey | Named highway bridge |

NJDOT's January 2024 Route 1 NB public-information flyer identifies the crossing
as Morris Goodkind Bridge (page 1, Background). Its historical schedule is not
used to update any current procurement dates. The registry binds the observed
Google destination, not Google's first-result ranking, to this official identity.

Remaining work: independently verify Bailey's Mill crossing; extend reviewed
structure entries selectively; model source-backed body project-location spans.
Do not buy a geocoding service or infer precision to increase link coverage.
