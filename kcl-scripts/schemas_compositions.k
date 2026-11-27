# Schemas for the composite kinds this repo defines and controls -- as
# opposed to schemas_providers.k, which models AWS provider resource shapes
# we depend on but don't own. Covers all four composite kinds; see each
# compose*.k file for where it's wired in.
schema BucketRef:
    name: str
    region: str

schema Zone:
    name: str
    id: str

schema StaticWebsiteSpec:
    # Crossplane injects spec.crossplane into every XR; it's not ours to model.
    crossplane?: any
    bucket: BucketRef
    zone?: Zone
    indexDocument?: str

schema IAMRoleSpec:
    # Crossplane injects spec.crossplane into every XR; it's not ours to model.
    crossplane?: any
    roleName: str
    trustedService: str
    description?: str
    managedPolicyArns?: [str]

schema LambdaCode:
    s3Bucket: str
    s3Key: str

schema LambdaFunctionSpec:
    # Crossplane injects spec.crossplane into every XR; it's not ours to model.
    crossplane?: any
    functionName: str
    runtime: str
    handler: str
    code: LambdaCode
    description?: str
    memorySize?: int
    timeoutSeconds?: int
    environmentVariables?: {str:str}
    managedPolicyArns?: [str]
    functionUrlEnabled?: bool

schema CertZoneRef:
    id: str

# DnsValidatedCertificate is a nested XR -- staticwebsite.k constructs an
# instance of this same schema when it creates one as a resource, same as
# this file's own oxr.spec.
schema DnsValidatedCertificateSpec:
    # Crossplane injects spec.crossplane into every XR; it's not ours to model.
    crossplane?: any
    domainName: str
    zone: CertZoneRef

