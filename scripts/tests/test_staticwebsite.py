import unittest

from crossplane.function import logging, resource, response
from crossplane.function.proto.v1 import run_function_pb2 as fnv1
from google.protobuf import json_format

from staticwebsite import compose

BASE_SPEC = {
    "bucket": {"name": "laz-static-website-customdomain-demo", "region": "ap-southeast-1"},
}


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


if __name__ == "__main__":
    unittest.main()
