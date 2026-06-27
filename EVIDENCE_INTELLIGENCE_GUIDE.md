# Evidence Intelligence Guide

RavenTech Evidence Intelligence is a defensive, analyst-driven layer that
summarizes recurring evidence across stored investigations. It does not perform
live enrichment, active scanning, exploitation, attribution, or automated action.

## What It Uses

Evidence Intelligence derives signals from local platform data only:

- Recon entities such as domains, subdomains, IP addresses, and technologies.
- Finding titles, severities, statuses, and remediation state.
- Finding evidence chains linked to recon entities or threat findings.
- Framework mappings stored in finding metadata.
- IOC observations synchronized from passive recon entities.
- Reports and investigations the current user is allowed to access.

Platform admins can see all stored investigations. Analysts and viewers only see
investigations available through membership or ownership.

## Recurrence Logic

An evidence item is considered recurring when it has either:

- Two or more stored observations, or
- Visibility in two or more accessible investigations.

Recurring categories include:

- Domains and subdomains
- IP addresses
- Technologies
- Finding patterns
- Defensive framework mappings
- Evidence chains

Each recurring item shows occurrence count, investigation count, first seen, last
seen, related investigations, linked findings, linked reports, and source count
where available.

## Confidence Scoring

Confidence is deterministic and evidence-count based.

| Confidence | Typical Indicators |
| --- | --- |
| Low | Single observation or limited source support |
| Medium | Multiple observations or multiple investigations |
| High | Recurrence plus source or finding corroboration |
| Very High | Frequent recurrence across investigations with corroborating sources/findings |

Inputs:

- Evidence frequency
- Investigation count
- Distinct source count
- Linked finding count

Confidence does not claim compromise. It only describes how strongly stored
evidence supports recurrence.

## Priority Logic

Investigation priority recommendations are deterministic.

Inputs:

- Unresolved finding severity
- Remediation backlog
- Recurring evidence count
- IOC observation count
- Internal correlation count

Output:

- Low
- Medium
- High
- Critical

The priority response includes an explanation list so analysts can see why a case
was elevated. No priority update is applied automatically.

## Timeline Logic

The intelligence timeline normalizes:

- First observed
- Repeated observation
- Remediation completed
- Recurrence after remediation linkage

Timeline entries are derived from stored timestamps and remediation state. They
are intended for analyst review and operational context.

## IOC Intelligence

The IOC view summarizes normalized indicators already stored in RavenTech:

- Seen in investigations
- Seen in findings
- Seen in reports
- Frequency
- First seen
- Last seen

It does not query external feeds or make threat actor attribution claims.

## Reporting

Reports include an Evidence Intelligence section when recurrence is visible for
the investigation. If no recurrence exists, reports render a clear empty-state
message rather than failing.

## Limitations

- Recurrence depends on stored data quality and accessible investigation scope.
- Missing or unmapped evidence will not appear until analysts generate findings
  or store recon evidence.
- Confidence is not a maliciousness score.
- Priority recommendations are advisory and require analyst approval.
- No external internet retrieval or active collection is performed.
