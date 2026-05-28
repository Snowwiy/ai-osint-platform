---
title: Defensive Detection Rule Handling
source: RavenTech curated starter knowledge
framework: Sigma
category: Detection Engineering
tags: sigma, yara, detection, validation
confidence: 0.8
created_at: 2026-05-28T00:00:00Z
---

# Detection rule handling

Detection rules should be treated as defensive monitoring content. Validate rule
scope, expected telemetry, false-positive conditions, and response ownership.

# Evidence use

Use Sigma and YARA references to explain detection coverage and evidence
collection needs. Do not infer compromise from a rule name alone.
