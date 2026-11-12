# Schemas for the AWS provider (Upbound) resource shapes we construct --
# the forProvider payloads this repo builds and sends to each Managed
# Resource. Scoped to each resource's forProvider only, not the observed
# status.atProvider side: that's data the provider controller hands back,
# arbitrarily deep, already read safely via `?.` -- a schema there would
# model someone else's CRD and drift with provider versions for no benefit.
# Covers every provider resource across all four composite kinds; see each
# compose*.k file for where it's wired in.
schema BucketForProvider:
    region: str

schema BucketPublicAccessBlockForProvider:
    blockPublicAcls: bool
    blockPublicPolicy: bool
    ignorePublicAcls: bool
    restrictPublicBuckets: bool
    bucket: str
    region: str

schema OriginAccessControlForProvider:
    originAccessControlOriginType: str
    signingBehavior: str
    signingProtocol: str
    name: str

schema BucketPolicyForProvider:
    bucket: str
    region: str
    policy: str

schema GeoRestriction:
    restrictionType: str

schema DistributionRestrictions:
    geoRestriction: GeoRestriction

schema DistributionOrigin:
    originId: str
    originAccessControlIdSelector: {str:bool}
    domainName: str

schema DefaultCacheBehavior:
    targetOriginId: str
    viewerProtocolPolicy: str
    allowedMethods: [str]
    cachedMethods: [str]
    cachePolicyId: str

schema DistributionForProvider:
    enabled: bool
    isIpv6Enabled: bool
    priceClass: str
    restrictions: DistributionRestrictions

    # Two mutually exclusive observed shapes (ACM cert vs. CloudFront
    # default cert, see staticwebsite.k's header comment on the gating bug)
    # that share no fields -- left loose rather than modeled as a schema
    # union.
    viewerCertificate: {str:any}
    origin: [DistributionOrigin]
    defaultCacheBehavior: DefaultCacheBehavior
    defaultRootObject?: str
    aliases?: [str]

schema RecordAlias:
    zoneId: str
    evaluateTargetHealth: bool
    name: str

schema DomainAliasRecordForProvider:
    type: str
    alias: RecordAlias
    name: str
    zoneId: str

schema RoleForProvider:
    assumeRolePolicy: str
    description?: str

schema RolePolicyAttachmentForProvider:
    policyArn: str
    role: str

schema LambdaEnvironment:
    variables: {str:str}

schema FunctionForProvider:
    role: str
    runtime: str
    handler: str
    s3Bucket: str
    s3Key: str
    description?: str
    memorySize?: int
    timeout?: int
    environment?: LambdaEnvironment

schema FunctionUrlForProvider:
    functionName: str
    authorizationType: str

schema CertificateForProvider:
    region: str
    validationMethod: str
    domainName: str

schema CertificateValidationForProvider:
    region: str
    certificateArn: str
    validationRecordFqdns: [str]

# The Route53 Record used by DnsValidatedCertificate's CNAME validation
# record -- a different shape from StaticWebsite's A/alias
# DomainAliasRecordForProvider above, despite both being kind: Record.
schema CertValidationRecordForProvider:
    type: str
    ttl: int
    name: str
    records: [str]
    zoneId: str

# The full set of forProvider shapes awsResource (staticwebsite.k) is ever
# called with -- named so its signature doesn't have to repeat this list.
type StaticWebsiteForProvider = BucketForProvider | BucketPublicAccessBlockForProvider | OriginAccessControlForProvider | BucketPolicyForProvider | DistributionForProvider | DomainAliasRecordForProvider
