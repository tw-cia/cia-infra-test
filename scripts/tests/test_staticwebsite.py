import json
import unittest

from crossplane.function import logging, resource, response
from crossplane.function.proto.v1 import run_function_pb2 as fnv1
from google.protobuf import json_format

from staticwebsite import compose

BASE_SPEC = {
    "bucket": {"name": "laz-static-website-customdomain-demo", "region": "ap-southeast-1"},
}

# Matches tests/fixtures/staticwebsite-xr-fully-observed.yaml -- the only
# scenario where bucket-policy and the Distribution both render (gated on
# status.distributionArn / status.certificateArn respectively).
FULLY_OBSERVED_SPEC = {
    "bucket": {"name": "laz-static-website-customdomain-demo", "region": "ap-southeast-1"},
    "zone": {"name": "static.trololo.demotw.com", "id": "Z00921083AT1Z6WZY8LYW"},
}
FULLY_OBSERVED_STATUS = {
    "bucketDomainName": "laz-static-website-customdomain-demo.s3.ap-southeast-1.amazonaws.com",
    "distributionArn": "arn:aws:cloudfront::123456789012:distribution/EDFDVBD6EXAMPLE",
    "certificateArn": "arn:aws:acm:us-east-1:123456789012:certificate/mock-certificate-id",
    "cloudfrontDomainName": "d111111abcdef8.cloudfront.net",
}

# Matches tests/fixtures/staticwebsite-xr-input-reflection.yaml -- values not
# shared with any other scenario here, so a passing assertion proves the
# value flowed from spec to the rendered resource, not coincidence.
INPUT_REFLECTION_SPEC = {
    "bucket": {"name": "reflection-test-bucket", "region": "eu-west-2"},
    "zone": {"name": "reflection.example.com", "id": "ZDISTINCTZONEID123"},
    "indexDocument": "home.html",
}
INPUT_REFLECTION_STATUS = {
    "bucketDomainName": "reflection-test-bucket.s3.eu-west-2.amazonaws.com",
    "certificateArn": "arn:aws:acm:us-east-1:999999999999:certificate/reflection-test-cert",
}


def make_request(spec: dict, status: dict | None = None) -> fnv1.RunFunctionRequest:
    xr = {
        "apiVersion": "platform.cia-infra-test.io/v1alpha1",
        "kind": "StaticWebsite",
        "spec": spec,
    }
    if status:
        xr["status"] = status
    return fnv1.RunFunctionRequest(
        observed=fnv1.State(composite=fnv1.Resource(resource=resource.dict_to_struct(xr))),
    )


class TestCompose(unittest.TestCase):
    def setUp(self) -> None:
        self.maxDiff = 4000
        logging.configure(level=logging.Level.DISABLED)

    def run_compose(self, req: fnv1.RunFunctionRequest) -> dict:
        rsp = response.to(req)
        compose(req, rsp)
        return json_format.MessageToDict(rsp)

    def test_composes_bucket_resources_on_cold_start(self) -> None:
        req = fnv1.RunFunctionRequest(
            observed=fnv1.State(
                composite=fnv1.Resource(
                    resource=resource.dict_to_struct(
                        {
                            "apiVersion": "platform.cia-infra-test.io/v1alpha1",
                            "kind": "StaticWebsite",
                            "spec": {
                                **BASE_SPEC,
                                "zone": {"name": "static.trololo.demotw.com", "id": "Z00921083AT1Z6WZY8LYW"},
                            },
                        }
                    ),
                ),
            ),
        )

        got = self.run_compose(req)

        resources = got["desired"]["resources"]
        self.assertEqual(
            set(resources),
            {"bucket", "bucket-public-access-block", "origin-access-control", "certificate"},
        )
        self.assertEqual(
            resources["bucket"]["resource"]["metadata"]["annotations"]["crossplane.io/external-name"],
            "laz-static-website-customdomain-demo",
        )
        self.assertEqual(resources["certificate"]["resource"]["kind"], "DnsValidatedCertificate")

    def test_omits_distribution_when_no_custom_domain_even_with_bucket_domain_known(self) -> None:
        # The known bug (see composition-staticwebsite-yaml-patching.yaml's
        # header comment): Distribution's viewerCertificate.acmCertificateArn
        # gate is unconditional, so a StaticWebsite with no custom zone can
        # never actually get a Distribution. This test exists to prove the
        # Python port faithfully reproduces that, not to celebrate it.
        req = fnv1.RunFunctionRequest(
            observed=fnv1.State(
                composite=fnv1.Resource(
                    resource=resource.dict_to_struct(
                        {
                            "apiVersion": "platform.cia-infra-test.io/v1alpha1",
                            "kind": "StaticWebsite",
                            "spec": BASE_SPEC,
                            "status": {
                                "bucketDomainName": "laz-static-website-customdomain-demo.s3.ap-southeast-1.amazonaws.com",
                            },
                        }
                    ),
                ),
            ),
        )

        got = self.run_compose(req)

        self.assertNotIn("distribution", got["desired"]["resources"])

    def test_composes_distribution_and_bucket_policy_once_fully_observed(self) -> None:
        req = fnv1.RunFunctionRequest(
            observed=fnv1.State(
                composite=fnv1.Resource(
                    resource=resource.dict_to_struct(
                        {
                            "apiVersion": "platform.cia-infra-test.io/v1alpha1",
                            "kind": "StaticWebsite",
                            "spec": {
                                **BASE_SPEC,
                                "zone": {"name": "static.trololo.demotw.com", "id": "Z00921083AT1Z6WZY8LYW"},
                            },
                            "status": {
                                "bucketDomainName": "laz-static-website-customdomain-demo.s3.ap-southeast-1.amazonaws.com",
                                "distributionArn": "arn:aws:cloudfront::123456789012:distribution/EDFDVBD6EXAMPLE",
                                "certificateArn": "arn:aws:acm:us-east-1:123456789012:certificate/mock-certificate-id",
                                "cloudfrontDomainName": "d111111abcdef8.cloudfront.net",
                            },
                        }
                    ),
                ),
            ),
        )

        got = self.run_compose(req)

        resources = got["desired"]["resources"]
        self.assertIn("distribution", resources)
        self.assertIn("bucket-policy", resources)
        self.assertIn("domain-alias-record", resources)

        distribution = resources["distribution"]["resource"]
        self.assertEqual(
            distribution["spec"]["forProvider"]["viewerCertificate"]["acmCertificateArn"],
            "arn:aws:acm:us-east-1:123456789012:certificate/mock-certificate-id",
        )

        policy = resources["bucket-policy"]["resource"]["spec"]["forProvider"]["policy"]
        self.assertIn("arn:aws:cloudfront::123456789012:distribution/EDFDVBD6EXAMPLE", policy)

    # Behaviour/CFR tests below -- mirror tests/behaviour/test_staticwebsite_security.py
    # and tests/behaviour/test_staticwebsite_input_reflection.py (which exercise this
    # same logic, and the other four implementations, via `crossplane
    # composition render`), and functions/staticwebsite/tests/test_fn.py
    # (the custom-packaged function's version of the same tests).

    def test_bucket_policy_grants_cloudfront_only(self) -> None:
        got = self.run_compose(make_request(FULLY_OBSERVED_SPEC, FULLY_OBSERVED_STATUS))

        policy_resource = got["desired"]["resources"]["bucket-policy"]["resource"]
        policy = policy_resource["spec"]["forProvider"]
        self.assertEqual(policy["bucket"], "laz-static-website-customdomain-demo")

        document = json.loads(policy["policy"])
        self.assertEqual(document["Version"], "2012-10-17")
        self.assertEqual(len(document["Statement"]), 1, "expected exactly one statement")

        statement = document["Statement"][0]
        self.assertEqual(statement["Effect"], "Allow")
        self.assertEqual(statement["Principal"], {"Service": "cloudfront.amazonaws.com"})
        self.assertEqual(statement["Resource"], "arn:aws:s3:::laz-static-website-customdomain-demo/*")
        self.assertEqual(
            statement["Condition"],
            {"StringEquals": {"AWS:SourceArn": "arn:aws:cloudfront::123456789012:distribution/EDFDVBD6EXAMPLE"}},
        )

    def test_bucket_policy_grants_get_object_only(self) -> None:
        got = self.run_compose(make_request(FULLY_OBSERVED_SPEC, FULLY_OBSERVED_STATUS))

        policy = got["desired"]["resources"]["bucket-policy"]["resource"]["spec"]["forProvider"]
        document = json.loads(policy["policy"])
        actions = [statement["Action"] for statement in document["Statement"]]
        self.assertEqual(actions, ["s3:GetObject"], f"granted actions beyond GetObject: {actions}")

    def test_requests_certificate_for_the_custom_domain(self) -> None:
        got = self.run_compose(make_request(FULLY_OBSERVED_SPEC, FULLY_OBSERVED_STATUS))

        certificate = got["desired"]["resources"]["certificate"]["resource"]["spec"]
        self.assertEqual(certificate["domainName"], "static.trololo.demotw.com")

        viewer_certificate = got["desired"]["resources"]["distribution"]["resource"]["spec"]["forProvider"][
            "viewerCertificate"
        ]
        self.assertEqual(
            viewer_certificate["acmCertificateArn"],
            "arn:aws:acm:us-east-1:123456789012:certificate/mock-certificate-id",
        )
        self.assertNotIn("cloudfrontDefaultCertificate", viewer_certificate)

    def test_distribution_enforces_tls_1_2_minimum(self) -> None:
        got = self.run_compose(make_request(FULLY_OBSERVED_SPEC, FULLY_OBSERVED_STATUS))

        viewer_certificate = got["desired"]["resources"]["distribution"]["resource"]["spec"]["forProvider"][
            "viewerCertificate"
        ]
        self.assertEqual(viewer_certificate["minimumProtocolVersion"], "TLSv1.2_2021")

    def test_blocks_all_public_access(self) -> None:
        got = self.run_compose(make_request(FULLY_OBSERVED_SPEC, FULLY_OBSERVED_STATUS))

        block = got["desired"]["resources"]["bucket-public-access-block"]["resource"]["spec"]["forProvider"]
        for flag in ("blockPublicAcls", "blockPublicPolicy", "ignorePublicAcls", "restrictPublicBuckets"):
            self.assertIs(block[flag], True, f"{flag} is not True")

    def test_public_access_block_targets_the_right_bucket(self) -> None:
        got = self.run_compose(make_request(FULLY_OBSERVED_SPEC, FULLY_OBSERVED_STATUS))

        bucket = got["desired"]["resources"]["bucket"]["resource"]
        bucket_name = bucket["metadata"]["annotations"]["crossplane.io/external-name"]
        bucket_region = bucket["spec"]["forProvider"]["region"]

        block = got["desired"]["resources"]["bucket-public-access-block"]["resource"]["spec"]["forProvider"]
        self.assertEqual(block["bucket"], bucket_name)
        self.assertEqual(block["region"], bucket_region)

    def test_origin_access_control_is_configured_correctly(self) -> None:
        got = self.run_compose(make_request(FULLY_OBSERVED_SPEC, FULLY_OBSERVED_STATUS))

        oac = got["desired"]["resources"]["origin-access-control"]["resource"]["spec"]["forProvider"]
        self.assertEqual(oac["originAccessControlOriginType"], "s3")
        self.assertEqual(oac["signingBehavior"], "always")
        self.assertEqual(oac["signingProtocol"], "sigv4")

    def test_distribution_selects_its_own_origin_access_control(self) -> None:
        got = self.run_compose(make_request(FULLY_OBSERVED_SPEC, FULLY_OBSERVED_STATUS))

        origin = got["desired"]["resources"]["distribution"]["resource"]["spec"]["forProvider"]["origin"][0]
        self.assertEqual(origin["originAccessControlIdSelector"], {"matchControllerRef": True})

    def test_bucket_reflects_name_and_region(self) -> None:
        got = self.run_compose(make_request(INPUT_REFLECTION_SPEC, INPUT_REFLECTION_STATUS))

        bucket = got["desired"]["resources"]["bucket"]["resource"]
        self.assertEqual(bucket["metadata"]["annotations"]["crossplane.io/external-name"], "reflection-test-bucket")
        self.assertEqual(bucket["spec"]["forProvider"]["region"], "eu-west-2")

    def test_distribution_reflects_index_document(self) -> None:
        got = self.run_compose(make_request(INPUT_REFLECTION_SPEC, INPUT_REFLECTION_STATUS))

        distribution = got["desired"]["resources"]["distribution"]["resource"]["spec"]["forProvider"]
        self.assertEqual(distribution["defaultRootObject"], "home.html")

    def test_distribution_reflects_custom_domain_alias(self) -> None:
        got = self.run_compose(make_request(INPUT_REFLECTION_SPEC, INPUT_REFLECTION_STATUS))

        distribution = got["desired"]["resources"]["distribution"]["resource"]["spec"]["forProvider"]
        self.assertEqual(distribution["aliases"], ["reflection.example.com"])


if __name__ == "__main__":
    unittest.main()
