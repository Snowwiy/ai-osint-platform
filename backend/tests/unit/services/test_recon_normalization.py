from __future__ import annotations

from app.schemas.recon import (
    CertificateRecord,
    CertificateResult,
    DNSRecordSet,
    DNSResult,
    HTTPResult,
    IPResult,
    RDAPResult,
    ReconResponse,
)
from app.services.recon.normalization import normalize_recon_entities


def test_entity_normalization_builds_entities_and_relationships() -> None:
    response = ReconResponse(
        target_type="domain",
        target_value="example.com",
        status="completed",
        dns=DNSResult(
            domain="example.com",
            records=[DNSRecordSet(record_type="A", values=["203.0.113.10"])],
        ),
        rdap=RDAPResult(
            query="example.com",
            target_type="domain",
            organizations=["Example Org"],
        ),
        certificates=CertificateResult(
            domain="example.com",
            certificates=[
                CertificateRecord(
                    certificate_id="123",
                    san_names=["www.example.com"],
                    issuer="Example CA",
                    expires_at="2030-01-01T00:00:00",
                )
            ],
            subdomains=["www.example.com"],
        ),
        ip=IPResult(ip_address="203.0.113.10", asn="AS64500", organization="Net Org"),
        http=HTTPResult(
            url="https://example.com",
            final_url="https://example.com",
            server="nginx",
            content_type="text/html",
        ),
    )

    graph = normalize_recon_entities(response)

    assert ("Domain", "example.com") in {
        (e.entity_type, e.value) for e in graph.entities
    }
    assert ("IPAddress", "203.0.113.10") in {
        (e.entity_type, e.value) for e in graph.entities
    }
    assert ("ASN", "AS64500") in {(e.entity_type, e.value) for e in graph.entities}
    assert ("USES_CERTIFICATE", "example.com", "123") in {
        (r.relationship_type, r.source_value, r.target_value)
        for r in graph.relationships
    }
