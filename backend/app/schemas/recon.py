from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

type JsonScalar = str | int | float | bool | None
type JsonProperties = dict[
    str, JsonScalar | list[str] | list[int] | list[float] | list[bool]
]

TargetType = Literal["domain", "ip", "url"]
EntityType = Literal[
    "Domain",
    "Subdomain",
    "IPAddress",
    "ASN",
    "Certificate",
    "Organization",
    "Service",
    "Technology",
]
RelationshipType = Literal[
    "RESOLVES_TO",
    "BELONGS_TO",
    "USES_CERTIFICATE",
    "HOSTS",
    "RELATED_TO",
    "DISCOVERED_FROM",
]
ReconStatus = Literal["completed", "partial", "failed"]
DNSRecordType = Literal["A", "AAAA", "MX", "TXT", "NS", "CNAME"]


class ReconError(BaseModel):
    source: str
    message: str


class ReconRequest(BaseModel):
    investigation_id: uuid.UUID
    target: str = Field(min_length=1, max_length=500)
    authorization_statement: str = Field(min_length=100, max_length=2000)

    @field_validator("target", "authorization_statement")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class DNSRecordSet(BaseModel):
    record_type: DNSRecordType
    values: list[str] = Field(default_factory=list)


class DNSResult(BaseModel):
    domain: str
    records: list[DNSRecordSet] = Field(default_factory=list)
    spf_records: list[str] = Field(default_factory=list)
    dmarc_records: list[str] = Field(default_factory=list)
    dkim_indicators: list[str] = Field(default_factory=list)
    errors: list[ReconError] = Field(default_factory=list)

    def record_values(self, record_type: DNSRecordType) -> list[str]:
        for record_set in self.records:
            if record_set.record_type == record_type:
                return record_set.values
        return []


class RDAPResult(BaseModel):
    query: str
    target_type: Literal["domain", "ip"]
    source: Literal["rdap", "whois", "none"] = "none"
    registrar: str | None = None
    registration_date: str | None = None
    expiration_date: str | None = None
    abuse_contacts: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)
    cidrs: list[str] = Field(default_factory=list)
    asn_references: list[str] = Field(default_factory=list)
    raw_handle: str | None = None
    errors: list[ReconError] = Field(default_factory=list)


class CertificateRecord(BaseModel):
    certificate_id: str
    san_names: list[str] = Field(default_factory=list)
    issuer: str | None = None
    expires_at: str | None = None


class CertificateResult(BaseModel):
    domain: str
    certificates: list[CertificateRecord] = Field(default_factory=list)
    subdomains: list[str] = Field(default_factory=list)
    errors: list[ReconError] = Field(default_factory=list)


class IPResult(BaseModel):
    ip_address: str
    asn: str | None = None
    provider: str | None = None
    organization: str | None = None
    country: str | None = None
    network_range: str | None = None
    cidrs: list[str] = Field(default_factory=list)
    errors: list[ReconError] = Field(default_factory=list)


class SecurityHeaders(BaseModel):
    hsts: str | None = None
    csp: str | None = None
    x_frame_options: str | None = None
    x_content_type_options: str | None = None
    referrer_policy: str | None = None


class CookieSummary(BaseModel):
    name: str
    secure: bool = False
    http_only: bool = False
    same_site: str | None = None


class TLSCertificateSummary(BaseModel):
    subject: str | None = None
    issuer: str | None = None
    not_before: str | None = None
    not_after: str | None = None
    san_names: list[str] = Field(default_factory=list)


class HTTPResult(BaseModel):
    url: str
    final_url: str | None = None
    status_code: int | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    security_headers: SecurityHeaders = Field(default_factory=SecurityHeaders)
    cookies: list[CookieSummary] = Field(default_factory=list)
    server: str | None = None
    content_type: str | None = None
    redirect_chain: list[str] = Field(default_factory=list)
    tls_version: str | None = None
    certificate: TLSCertificateSummary | None = None
    errors: list[ReconError] = Field(default_factory=list)


class NormalizedEntity(BaseModel):
    entity_type: EntityType
    value: str
    display_name: str | None = None
    properties: JsonProperties = Field(default_factory=dict)
    source: str | None = None


class NormalizedRelationship(BaseModel):
    relationship_type: RelationshipType
    source_type: EntityType
    source_value: str
    target_type: EntityType
    target_value: str
    properties: JsonProperties = Field(default_factory=dict)
    source: str | None = None


class ReconGraph(BaseModel):
    entities: list[NormalizedEntity] = Field(default_factory=list)
    relationships: list[NormalizedRelationship] = Field(default_factory=list)


class ReconResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    investigation_id: uuid.UUID | None = None
    enrichment_id: uuid.UUID | None = None
    target_type: TargetType
    target_value: str
    status: ReconStatus
    dns: DNSResult | None = None
    rdap: RDAPResult | None = None
    certificates: CertificateResult | None = None
    ip: IPResult | None = None
    http: HTTPResult | None = None
    entities: list[NormalizedEntity] = Field(default_factory=list)
    relationships: list[NormalizedRelationship] = Field(default_factory=list)
    errors: list[ReconError] = Field(default_factory=list)
