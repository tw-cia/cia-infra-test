"""Proves security-relevant properties of the rendered StaticWebsite
resources themselves, for every implementation -- not that the
implementations agree with each other (that's test_equivalence.py), but that
what they produce is actually what we intend to run: the bucket has no
public access, and the only thing allowed to read it is this bucket's own
CloudFront distribution.

Shares test_equivalence.py's render harness (same requirements: the three
function-*:dev images built locally, and the `jsonnet` CLI on PATH -- see
that file's docstring for the exact commands).
"""

import pytest

from test_equivalence import METHODS, find_one, render_method


# Matches tests/fixtures/staticwebsite-xr-fully-observed.yaml's spec/status --
# the only scenario where bucket-policy actually renders (gated on
# status.distributionArn).
FULLY_OBSERVED_BUCKET_NAME = "laz-static-website-customdomain-demo"
FULLY_OBSERVED_DISTRIBUTION_ARN = "arn:aws:cloudfront::123456789012:distribution/EDFDVBD6EXAMPLE"
FULLY_OBSERVED_ZONE_NAME = "static.trololo.demotw.com"
FULLY_OBSERVED_CERTIFICATE_ARN = "arn:aws:acm:us-east-1:123456789012:certificate/mock-certificate-id"


@pytest.mark.parametrize("method", METHODS)
def test_staticwebsite_bucket_policy_grants_cloudfront_only(method):
    """The bucket policy that lets CloudFront read the bucket should grant
    nothing else: one statement, scoped to the cloudfront.amazonaws.com
    service principal and this bucket's one distribution, not a wildcard
    principal or resource."""
    xr = "tests/fixtures/staticwebsite-xr-fully-observed.yaml"
    docs = render_method(method, xr, "staticwebsite")

    policy = find_one(docs, "BucketPolicy")["spec"]["forProvider"]
    assert policy["bucket"] == FULLY_OBSERVED_BUCKET_NAME

    # normalize()'s _parse_json_strings already parsed this from a JSON
    # string into a dict, so this is the actual policy document, not text.
    document = policy["policy"]
    assert document["Version"] == "2012-10-17"
    assert len(document["Statement"]) == 1, "expected exactly one statement"

    statement = document["Statement"][0]
    assert statement["Effect"] == "Allow"
    assert statement["Principal"] == {"Service": "cloudfront.amazonaws.com"}, (
        "principal isn't scoped to CloudFront alone"
    )
    assert statement["Action"] == "s3:GetObject"
    assert statement["Resource"] == f"arn:aws:s3:::{FULLY_OBSERVED_BUCKET_NAME}/*"
    assert statement["Condition"] == {"StringEquals": {"AWS:SourceArn": FULLY_OBSERVED_DISTRIBUTION_ARN}}, (
        "not scoped to this bucket's distribution alone"
    )


@pytest.mark.parametrize("method", METHODS)
def test_staticwebsite_bucket_policy_grants_get_object_only(method):
    """The one thing CloudFront is allowed to do to the bucket is read
    objects -- not write, delete, list, or anything else."""
    xr = "tests/fixtures/staticwebsite-xr-fully-observed.yaml"
    docs = render_method(method, xr, "staticwebsite")

    document = find_one(docs, "BucketPolicy")["spec"]["forProvider"]["policy"]
    actions = [statement["Action"] for statement in document["Statement"]]
    assert actions == ["s3:GetObject"], f"granted actions beyond GetObject: {actions}"


@pytest.mark.parametrize("method", METHODS)
def test_staticwebsite_requests_certificate_for_the_custom_domain(method):
    """Setting a custom domain should request an ACM certificate for that
    exact domain, via the nested DnsValidatedCertificate composite -- and
    the Distribution should actually be wired to use that certificate's
    ARN, not fall back to the default CloudFront certificate."""
    xr = "tests/fixtures/staticwebsite-xr-fully-observed.yaml"
    docs = render_method(method, xr, "staticwebsite")

    certificate = find_one(docs, "DnsValidatedCertificate")["spec"]
    assert certificate["domainName"] == FULLY_OBSERVED_ZONE_NAME

    viewer_certificate = find_one(docs, "Distribution")["spec"]["forProvider"]["viewerCertificate"]
    assert viewer_certificate["acmCertificateArn"] == FULLY_OBSERVED_CERTIFICATE_ARN
    assert "cloudfrontDefaultCertificate" not in viewer_certificate


@pytest.mark.parametrize("method", METHODS)
def test_staticwebsite_distribution_enforces_tls_1_2_minimum(method):
    """TLSv1.2_2021 is AWS's enum for "TLS 1.2 minimum, 2021 cipher suite
    set" on a custom-domain viewer certificate -- anything weaker (TLSv1,
    TLSv1.1, SSLv3) is rejected."""
    xr = "tests/fixtures/staticwebsite-xr-fully-observed.yaml"
    docs = render_method(method, xr, "staticwebsite")

    viewer_certificate = find_one(docs, "Distribution")["spec"]["forProvider"]["viewerCertificate"]
    assert viewer_certificate["minimumProtocolVersion"] == "TLSv1.2_2021"


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize(
    "xr",
    [
        "tests/fixtures/static-website-customdomain-example.yaml",
        "tests/fixtures/staticwebsite-xr-no-zone.yaml",
        "tests/fixtures/staticwebsite-xr-partial-observed.yaml",
        "tests/fixtures/staticwebsite-xr-fully-observed.yaml",
    ],
    ids=["cold-start", "no-custom-domain-bug", "certificate-not-yet-known", "fully-observed"],
)
def test_staticwebsite_blocks_all_public_access(xr, method):
    """BucketPublicAccessBlock isn't gated on anything -- it should render,
    with every flag set, in every scenario, for every method."""
    docs = render_method(method, xr, "staticwebsite")
    block = find_one(docs, "BucketPublicAccessBlock")["spec"]["forProvider"]
    for flag in ("blockPublicAcls", "blockPublicPolicy", "ignorePublicAcls", "restrictPublicBuckets"):
        assert block[flag] is True, f"{flag} is not True"


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize(
    "xr",
    [
        "tests/fixtures/static-website-customdomain-example.yaml",
        "tests/fixtures/staticwebsite-xr-no-zone.yaml",
        "tests/fixtures/staticwebsite-xr-partial-observed.yaml",
        "tests/fixtures/staticwebsite-xr-fully-observed.yaml",
    ],
    ids=["cold-start", "no-custom-domain-bug", "certificate-not-yet-known", "fully-observed"],
)
def test_staticwebsite_public_access_block_targets_the_right_bucket(xr, method):
    """blocks_all_public_access proves the four flags are set -- this proves
    they're set against *this* bucket, in *this* region, not just set
    somewhere. Checked against the actual rendered Bucket, not a hardcoded
    constant, so it proves the coupling rather than two independent facts
    that happen to agree."""
    docs = render_method(method, xr, "staticwebsite")

    bucket = find_one(docs, "Bucket")
    bucket_name = bucket["metadata"]["annotations"]["crossplane.io/external-name"]
    bucket_region = bucket["spec"]["forProvider"]["region"]

    block = find_one(docs, "BucketPublicAccessBlock")["spec"]["forProvider"]
    assert block["bucket"] == bucket_name
    assert block["region"] == bucket_region


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize(
    "xr",
    [
        "tests/fixtures/static-website-customdomain-example.yaml",
        "tests/fixtures/staticwebsite-xr-no-zone.yaml",
        "tests/fixtures/staticwebsite-xr-partial-observed.yaml",
        "tests/fixtures/staticwebsite-xr-fully-observed.yaml",
    ],
    ids=["cold-start", "no-custom-domain-bug", "certificate-not-yet-known", "fully-observed"],
)
def test_staticwebsite_origin_access_control_is_configured_correctly(xr, method):
    """The bucket-policy tests prove CloudFront is the only thing *allowed*
    to read the bucket -- that only holds if the OriginAccessControl itself
    actually signs requests the way the policy expects: SigV4, always, for
    an S3 origin. Get any of these wrong and CloudFront can't read the
    bucket at all, or silently stops signing requests."""
    docs = render_method(method, xr, "staticwebsite")
    oac = find_one(docs, "OriginAccessControl")["spec"]["forProvider"]
    assert oac["originAccessControlOriginType"] == "s3"
    assert oac["signingBehavior"] == "always"
    assert oac["signingProtocol"] == "sigv4"


@pytest.mark.parametrize("method", METHODS)
def test_staticwebsite_distribution_selects_its_own_origin_access_control(method):
    """Not just "an OAC exists and is configured correctly" -- the
    Distribution has to actually select *this* OAC. matchControllerRef scopes
    the selection to resources owned by the same composite, so this
    Distribution can't accidentally bind to some other StaticWebsite's OAC."""
    xr = "tests/fixtures/staticwebsite-xr-fully-observed.yaml"
    docs = render_method(method, xr, "staticwebsite")
    origin = find_one(docs, "Distribution")["spec"]["forProvider"]["origin"][0]
    assert origin["originAccessControlIdSelector"] == {"matchControllerRef": True}
