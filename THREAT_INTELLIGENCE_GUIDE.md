# Threat Intelligence Workspace Guide

RavenTech OSINT's Threat Intelligence Workspace is a defensive, evidence-backed
view of indicators, analyst-created campaigns, analyst-approved threat groups,
MITRE ATT&CK mappings, and recurring infrastructure.

It is designed for internal investigation maturity. It does not perform active
scanning, internet-wide enumeration, automatic attribution, malware analysis, or
offensive workflow execution.

## Scope

The workspace organizes stored platform data:

- Indicators observed through investigations and IOC records.
- Recurring domains, subdomains, IPs, technologies, certificates, and hosting
  references from passive recon entities.
- Analyst-created campaign records.
- Analyst-approved threat group context.
- Evidence-backed ATT&CK technique mappings from findings, campaigns, and
  groups.
- Threat intelligence timeline events derived from stored observations and
  analyst workflow activity.

## Indicator Repository

Indicators may include:

- IP addresses
- Domains and subdomains
- URLs
- Emails
- Hashes
- Hostnames

Each indicator summary shows:

- First seen and last seen timestamps.
- Occurrence count.
- Related investigation count.
- Related findings and reports count.
- Confidence and confidence reasoning.
- Linked investigations for navigation.

Indicator recurrence is internal only. Seeing an indicator in multiple
investigations does not imply attribution or compromise.

## Confidence Model

Threat intelligence confidence is deterministic:

- **Low**: Limited evidence, single observation, or no analyst validation.
- **Medium**: Multiple observations, some corroboration, or recurring internal
  evidence.
- **High**: Strong recurrence, multiple corroborating signals, or substantial
  finding linkage.
- **Confirmed**: Analyst validation plus strong corroboration.

Confidence considers:

- Evidence count.
- Corroboration count.
- Investigation recurrence.
- Analyst validation.

The score does not use AI and does not make unsupported claims.

## Campaign Workflow

Campaigns are analyst-created groupings of related observations.

Use campaigns when there is enough evidence to group:

- Indicators
- Findings
- Investigations
- ATT&CK techniques

Recommended workflow:

1. Review recurring indicators and infrastructure.
2. Confirm related investigations and findings.
3. Create a campaign only when the relationship is evidence-backed.
4. Add technique mappings where relevant.
5. Update campaign confidence as analyst validation improves.

Campaigns should be named descriptively and defensively, such as
"Recurring exposed infrastructure review" or "Shared DNS configuration concern."

## Threat Group Workflow

Threat groups are analyst-approved context. RavenTech OSINT does not infer or
assign attribution automatically.

Use group records only when:

- Supporting evidence exists.
- The analyst has documented confidence and notes.
- The relationship to campaigns, indicators, or techniques is defensible.

Avoid unsupported labels and breach claims. Use cautious language such as
"observed overlap", "potentially related", and "requires analyst validation."

## ATT&CK Mapping Workflow

ATT&CK mappings can connect:

- Findings to techniques.
- Campaigns to techniques.
- Threat groups to techniques.

Mappings must explain why they exist. Relevant examples include:

- A finding contains a stored technique reference.
- A campaign has repeated indicators tied to a defensive observation.
- An analyst links a group to a technique based on validated context.

Do not force mappings. If evidence does not support a technique, leave it
unmapped.

## Infrastructure Recurrence Logic

Infrastructure intelligence is derived from stored recon entities:

- Domains and subdomains
- IP addresses
- Technologies
- Certificates
- ASN and organization references

Recurring infrastructure appears when the same value is observed multiple times
or across investigations. This helps analysts identify repeated exposure,
shared dependencies, and defensive review priorities.

## Timeline Events

The threat timeline may include:

- Indicator observed.
- Indicator repeated.
- Campaign created or updated.
- Threat group linked.
- ATT&CK technique mapped.
- Remediation completed.

Timeline events are intended for analyst orientation and report context.

## Reporting Integration

Reports may include a Threat Intelligence section with:

- Indicator summaries.
- Recurring infrastructure.
- ATT&CK mapping counts.
- Confidence labels.

If no threat intelligence data exists, reports include an empty-state statement
instead of failing.

## Limitations

- No external threat feed enrichment is performed.
- No automatic threat actor attribution is performed.
- No offensive actions or active scanning are available.
- Confidence is deterministic and based on stored evidence only.
- Analyst review is required for campaign and threat group context.

