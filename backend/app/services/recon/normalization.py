from __future__ import annotations

from urllib.parse import urlparse

from app.schemas.recon import (
    DNSRecordType,
    JsonProperties,
    NormalizedEntity,
    NormalizedRelationship,
    ReconGraph,
    ReconResponse,
)


def normalize_recon_entities(response: ReconResponse) -> ReconGraph:
    builder = _GraphBuilder()
    root_type, root_value = _root_entity(response)
    builder.entity(root_type, root_value, source="target")

    if response.dns:
        builder.entity("Domain", response.dns.domain, source="dns")
        address_records: tuple[DNSRecordType, ...] = ("A", "AAAA")
        for record_type in address_records:
            for value in response.dns.record_values(record_type):
                builder.entity("IPAddress", value, source="dns")
                builder.relationship(
                    "RESOLVES_TO",
                    "Domain",
                    response.dns.domain,
                    "IPAddress",
                    value,
                    source="dns",
                )
        host_records: tuple[DNSRecordType, ...] = ("MX", "NS", "CNAME")
        for record_type in host_records:
            for value in response.dns.record_values(record_type):
                host = value.split()[-1].rstrip(".").lower()
                builder.entity("Subdomain", host, source="dns")
                builder.relationship(
                    "RELATED_TO",
                    "Domain",
                    response.dns.domain,
                    "Subdomain",
                    host,
                    {"record_type": record_type},
                    source="dns",
                )

    if response.rdap:
        for organization in response.rdap.organizations:
            builder.entity("Organization", organization, source=response.rdap.source)
            builder.relationship(
                "RELATED_TO",
                root_type,
                root_value,
                "Organization",
                organization,
                source=response.rdap.source,
            )
        for asn in response.rdap.asn_references:
            normalized_asn = asn if asn.upper().startswith("AS") else f"AS{asn}"
            builder.entity("ASN", normalized_asn, source=response.rdap.source)
            builder.relationship(
                "RELATED_TO",
                root_type,
                root_value,
                "ASN",
                normalized_asn,
                source=response.rdap.source,
            )

    if response.certificates:
        domain = response.certificates.domain
        builder.entity("Domain", domain, source="crt.sh")
        for subdomain in response.certificates.subdomains:
            builder.entity("Subdomain", subdomain, source="crt.sh")
            builder.relationship(
                "DISCOVERED_FROM",
                "Subdomain",
                subdomain,
                "Domain",
                domain,
                source="crt.sh",
            )
        for cert in response.certificates.certificates:
            builder.entity(
                "Certificate",
                cert.certificate_id,
                display_name=cert.issuer,
                properties={"expires_at": cert.expires_at, "san_names": cert.san_names},
                source="crt.sh",
            )
            builder.relationship(
                "USES_CERTIFICATE",
                "Domain",
                domain,
                "Certificate",
                cert.certificate_id,
                source="crt.sh",
            )

    if response.ip:
        builder.entity("IPAddress", response.ip.ip_address, source="ip-rdap")
        if response.ip.asn:
            builder.entity(
                "ASN",
                response.ip.asn,
                properties={
                    "provider": response.ip.provider,
                    "country": response.ip.country,
                    "network_range": response.ip.network_range,
                },
                source="ip-rdap",
            )
            builder.relationship(
                "BELONGS_TO",
                "IPAddress",
                response.ip.ip_address,
                "ASN",
                response.ip.asn,
                source="ip-rdap",
            )
        if response.ip.organization:
            builder.entity("Organization", response.ip.organization, source="ip-rdap")
            if response.ip.asn:
                builder.relationship(
                    "BELONGS_TO",
                    "ASN",
                    response.ip.asn,
                    "Organization",
                    response.ip.organization,
                    source="ip-rdap",
                )

    if response.http:
        service_value = response.http.final_url or response.http.url
        builder.entity(
            "Service",
            service_value,
            properties={
                "status_code": response.http.status_code,
                "content_type": response.http.content_type,
            },
            source="http",
        )
        builder.relationship(
            "HOSTS",
            root_type,
            root_value,
            "Service",
            service_value,
            source="http",
        )
        if response.http.server:
            builder.entity("Technology", response.http.server, source="http")
            builder.relationship(
                "RELATED_TO",
                "Service",
                service_value,
                "Technology",
                response.http.server,
                source="http",
            )

    return builder.graph()


class _GraphBuilder:
    def __init__(self) -> None:
        self._entities: dict[tuple[str, str], NormalizedEntity] = {}
        self._relationships: dict[
            tuple[str, str, str, str, str],
            NormalizedRelationship,
        ] = {}

    def entity(
        self,
        entity_type: str,
        value: str,
        *,
        display_name: str | None = None,
        properties: JsonProperties | None = None,
        source: str | None = None,
    ) -> None:
        clean_value = (
            value.strip().lower()
            if entity_type in ("Domain", "Subdomain")
            else value.strip()
        )
        if not clean_value:
            return
        key = (entity_type, clean_value)
        if key not in self._entities:
            self._entities[key] = NormalizedEntity(
                entity_type=entity_type,  # type: ignore[arg-type]
                value=clean_value,
                display_name=display_name,
                properties=_drop_none(properties or {}),
                source=source,
            )

    def relationship(
        self,
        relationship_type: str,
        source_type: str,
        source_value: str,
        target_type: str,
        target_value: str,
        properties: JsonProperties | None = None,
        *,
        source: str | None = None,
    ) -> None:
        normalized_source = (
            source_value.strip().lower()
            if source_type in ("Domain", "Subdomain")
            else source_value.strip()
        )
        normalized_target = (
            target_value.strip().lower()
            if target_type in ("Domain", "Subdomain")
            else target_value.strip()
        )
        key = (
            relationship_type,
            source_type,
            normalized_source,
            target_type,
            normalized_target,
        )
        if key not in self._relationships:
            self._relationships[key] = NormalizedRelationship(
                relationship_type=relationship_type,  # type: ignore[arg-type]
                source_type=source_type,  # type: ignore[arg-type]
                source_value=normalized_source,
                target_type=target_type,  # type: ignore[arg-type]
                target_value=normalized_target,
                properties=_drop_none(properties or {}),
                source=source,
            )

    def graph(self) -> ReconGraph:
        return ReconGraph(
            entities=list(self._entities.values()),
            relationships=list(self._relationships.values()),
        )


def _root_entity(response: ReconResponse) -> tuple[str, str]:
    if response.target_type == "ip":
        return "IPAddress", response.target_value
    if response.target_type == "url":
        host = urlparse(response.target_value).hostname or response.target_value
        return ("IPAddress", host) if _looks_like_ip(host) else ("Domain", host)
    return "Domain", response.target_value


def _looks_like_ip(value: str) -> bool:
    return (
        all(
            part.isdigit() and 0 <= int(part) <= 255
            for part in value.split(".")
            if part
        )
        and value.count(".") == 3
    )


def _drop_none(properties: JsonProperties) -> JsonProperties:
    return {key: value for key, value in properties.items() if value is not None}
