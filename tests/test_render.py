import subprocess

import jmespath
import pytest
import yaml

RENDER_COMMAND = [
    "crossplane",
    "composition",
    "render",
    "tests/fixtures/static-website-customdomain-example.yaml",
    "./manifests/crossplane-compositions/yaml-patching/composition-staticwebsite-yaml-patching.yaml",
    "./manifests/crossplane-compositions/yaml-patching/function-patch-and-transform.yaml",
]

# The ACM Certificate is no longer composed directly by StaticWebsite -- it's
# one hop deeper, behind the nested DnsValidatedCertificate XR (see
# composition-dnsvalidatedcertificate.yaml). To see the real Certificate
# resource, render StaticWebsite first, then render whatever
# DnsValidatedCertificate it produced through its own Composition.
CERTIFICATE_RENDER_COMMAND = [
    "crossplane",
    "composition",
    "render",
    "/dev/stdin",
    "./manifests/crossplane-compositions/yaml-patching/composition-dnsvalidatedcertificate-yaml-patching.yaml",
    "./manifests/crossplane-compositions/yaml-patching/function-patch-and-transform.yaml",
]


@pytest.fixture(scope="module")
def render_result():
    return subprocess.run(RENDER_COMMAND, capture_output=True, text=True)


@pytest.fixture(scope="module")
def certificate_render_result(render_result):
    documents = list(yaml.safe_load_all(render_result.stdout))
    certificate_xr = jmespath.search("[?kind=='DnsValidatedCertificate'] | [0]", documents)
    assert certificate_xr is not None

    return subprocess.run(
        CERTIFICATE_RENDER_COMMAND,
        input=yaml.dump(certificate_xr),
        capture_output=True,
        text=True,
    )


def test_render_exits_zero(render_result):
    assert render_result.returncode == 0, render_result.stderr


def test_render_outputs_yaml(render_result):
    documents = list(yaml.safe_load_all(render_result.stdout))
    assert len(documents) > 0


def test_render_includes_acm_certificate(certificate_render_result):
    documents = list(yaml.safe_load_all(certificate_render_result.stdout))

    for document in documents:
        assert isinstance(document, dict)

    matches = jmespath.search("[?apiVersion=='acm.aws.m.upbound.io/v1beta1']", documents)
    assert matches


def test_render_acm_certificate_domain_name(certificate_render_result):
    documents = list(yaml.safe_load_all(certificate_render_result.stdout))

    domain_name = jmespath.search(
        "[?apiVersion=='acm.aws.m.upbound.io/v1beta1'] | [0].spec.forProvider.domainName",
        documents,
    )

    assert domain_name == "static.trololo.demotw.com"


def test_render_omits_bucket_policy_when_distribution_not_yet_observed(render_result):
    documents = list(yaml.safe_load_all(render_result.stdout))

    # BucketPolicy's policy field is gated on status.distributionArn, which
    # a cold render (no observed resources, no prior status) never has --
    # so it shouldn't render at all yet, same as the DnsValidatedCertificate
    # gated resources above.
    assert jmespath.search("[?kind=='BucketPolicy']", documents) == []


STATICWEBSITE_RENDER_COMMAND_OBSERVED = [
    "crossplane",
    "composition",
    "render",
    "tests/fixtures/staticwebsite-xr-observed.yaml",
    "./manifests/crossplane-compositions/yaml-patching/composition-staticwebsite-yaml-patching.yaml",
    "./manifests/crossplane-compositions/yaml-patching/function-patch-and-transform.yaml",
]


@pytest.fixture(scope="module")
def staticwebsite_render_result_observed():
    return subprocess.run(STATICWEBSITE_RENDER_COMMAND_OBSERVED, capture_output=True, text=True)


def test_render_bucket_policy_matches_bucket_once_distribution_observed(
    staticwebsite_render_result_observed,
):
    assert staticwebsite_render_result_observed.returncode == 0, staticwebsite_render_result_observed.stderr
    documents = list(yaml.safe_load_all(staticwebsite_render_result_observed.stdout))

    bucket_name = jmespath.search(
        "[?kind=='Bucket'] | [0].metadata.annotations.\"crossplane.io/external-name\"",
        documents,
    )
    policy = jmespath.search("[?kind=='BucketPolicy'] | [0]", documents)

    assert bucket_name is not None
    assert policy is not None
    assert policy["spec"]["forProvider"]["bucket"] == bucket_name
    assert "arn:aws:cloudfront::123456789012:distribution/EDFDVBD6EXAMPLE" in policy["spec"]["forProvider"]["policy"]


# Tests for composition-dnsvalidatedcertificate.yaml standalone, rather than
# through StaticWebsite. Rendered cold (no observed resources) and again with
# a mocked observed Certificate, since cert-validation-record and
# certificate-validation are both gated on that Certificate's status and
# never render on a cold start.
DNS_CERT_RENDER_COMMAND = [
    "crossplane",
    "composition",
    "render",
    "tests/fixtures/dns-validated-certificate-example.yaml",
    "./manifests/crossplane-compositions/yaml-patching/composition-dnsvalidatedcertificate-yaml-patching.yaml",
    "./manifests/crossplane-compositions/yaml-patching/function-patch-and-transform.yaml",
]

DNS_CERT_RENDER_COMMAND_OBSERVED = [
    "crossplane",
    "composition",
    "render",
    # A variant of the XR with status pre-populated, simulating a later
    # reconcile -- see the fixture file's comment for why this is needed in
    # addition to --observed-resources.
    "tests/fixtures/dns-validated-certificate-xr-observed.yaml",
    "./manifests/crossplane-compositions/yaml-patching/composition-dnsvalidatedcertificate-yaml-patching.yaml",
    "./manifests/crossplane-compositions/yaml-patching/function-patch-and-transform.yaml",
    "--observed-resources=tests/fixtures/dns-validated-certificate-observed.yaml",
]


@pytest.fixture(scope="module")
def dns_cert_render_result():
    return subprocess.run(DNS_CERT_RENDER_COMMAND, capture_output=True, text=True)


@pytest.fixture(scope="module")
def dns_cert_render_result_observed():
    return subprocess.run(DNS_CERT_RENDER_COMMAND_OBSERVED, capture_output=True, text=True)


def test_dns_cert_render_exits_zero(dns_cert_render_result):
    assert dns_cert_render_result.returncode == 0, dns_cert_render_result.stderr


def test_dns_cert_render_includes_certificate(dns_cert_render_result):
    documents = list(yaml.safe_load_all(dns_cert_render_result.stdout))

    domain_name = jmespath.search(
        "[?apiVersion=='acm.aws.m.upbound.io/v1beta1'] | [0].spec.forProvider.domainName",
        documents,
    )

    assert domain_name == "static-two.trololo.demotw.com"


def test_dns_cert_render_omits_validation_resources_when_certificate_not_yet_observed(
    dns_cert_render_result,
):
    documents = list(yaml.safe_load_all(dns_cert_render_result.stdout))

    assert jmespath.search("[?kind=='Record']", documents) == []
    assert jmespath.search("[?kind=='CertificateValidation']", documents) == []


def test_dns_cert_render_includes_validation_record_once_certificate_observed(
    dns_cert_render_result_observed,
):
    assert dns_cert_render_result_observed.returncode == 0, dns_cert_render_result_observed.stderr
    documents = list(yaml.safe_load_all(dns_cert_render_result_observed.stdout))

    record = jmespath.search("[?kind=='Record'] | [0]", documents)
    assert record is not None
    assert record["spec"]["forProvider"]["name"] == "_acmvalidation.static-two.trololo.demotw.com."
    assert record["spec"]["forProvider"]["records"] == ["validate.acm-validations.aws."]
    assert record["spec"]["forProvider"]["zoneId"] == "Z00921083AT1Z6WZY8LYW"


def test_dns_cert_render_includes_certificate_validation_once_certificate_observed(
    dns_cert_render_result_observed,
):
    documents = list(yaml.safe_load_all(dns_cert_render_result_observed.stdout))

    validation = jmespath.search("[?kind=='CertificateValidation'] | [0]", documents)
    assert validation is not None
    assert (
        validation["spec"]["forProvider"]["certificateArn"]
        == "arn:aws:acm:us-east-1:123456789012:certificate/mock-certificate-id"
    )
    assert validation["spec"]["forProvider"]["validationRecordFqdns"] == [
        "_acmvalidation.static-two.trololo.demotw.com."
    ]
