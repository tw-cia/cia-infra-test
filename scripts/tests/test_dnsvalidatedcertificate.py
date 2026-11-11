import unittest

from crossplane.function import logging, resource, response
from crossplane.function.proto.v1 import run_function_pb2 as fnv1
from google.protobuf import duration_pb2 as durationpb
from google.protobuf import json_format
from google.protobuf import struct_pb2 as structpb

from dnsvalidatedcertificate import compose

PROVIDER_CONFIG = {"kind": "ClusterProviderConfig", "name": "pod-identity"}

BASE_SPEC = {
    "domainName": "static.trololo.demotw.com",
    "zone": {"id": "Z00921083AT1Z6WZY8LYW"},
}


class TestCompose(unittest.TestCase):
    def setUp(self) -> None:
        self.maxDiff = 4000
        logging.configure(level=logging.Level.DISABLED)

    def run_compose(self, req: fnv1.RunFunctionRequest) -> dict:
        rsp = response.to(req)
        compose(req, rsp)
        return json_format.MessageToDict(rsp)

    def test_composes_certificate_only_when_not_yet_observed(self) -> None:
        req = fnv1.RunFunctionRequest(
            observed=fnv1.State(
                composite=fnv1.Resource(
                    resource=resource.dict_to_struct(
                        {
                            "apiVersion": "platform.cia-infra-test.io/v1alpha1",
                            "kind": "DnsValidatedCertificate",
                            "spec": BASE_SPEC,
                        }
                    ),
                ),
            ),
        )

        want = fnv1.RunFunctionResponse(
            meta=fnv1.ResponseMeta(ttl=durationpb.Duration(seconds=60)),
            desired=fnv1.State(
                resources={
                    "certificate": fnv1.Resource(
                        resource=resource.dict_to_struct(
                            {
                                "apiVersion": "acm.aws.m.upbound.io/v1beta1",
                                "kind": "Certificate",
                                "spec": {
                                    "forProvider": {
                                        "region": "us-east-1",
                                        "validationMethod": "DNS",
                                        "domainName": "static.trololo.demotw.com",
                                    },
                                    "providerConfigRef": PROVIDER_CONFIG,
                                },
                            }
                        ),
                    ),
                },
            ),
            context=structpb.Struct(),
        )

        got = self.run_compose(req)

        self.assertEqual(json_format.MessageToDict(want), got, "-want, +got")

    def test_surfaces_status_but_not_validation_resources_once_certificate_observed(self) -> None:
        req = fnv1.RunFunctionRequest(
            observed=fnv1.State(
                composite=fnv1.Resource(
                    resource=resource.dict_to_struct(
                        {
                            "apiVersion": "platform.cia-infra-test.io/v1alpha1",
                            "kind": "DnsValidatedCertificate",
                            "spec": BASE_SPEC,
                        }
                    ),
                ),
                resources={
                    "certificate": fnv1.Resource(
                        resource=resource.dict_to_struct(
                            {
                                "status": {
                                    "atProvider": {
                                        "arn": "arn:aws:acm:us-east-1:123456789012:certificate/mock-certificate-id",
                                        "domainValidationOptions": [
                                            {
                                                "resourceRecordName": "_acmvalidation.static.trololo.demotw.com.",
                                                "resourceRecordValue": "validate.acm-validations.aws.",
                                            }
                                        ],
                                    },
                                },
                            }
                        ),
                    ),
                },
            ),
        )

        got = self.run_compose(req)

        self.assertEqual(
            got["desired"]["composite"]["resource"]["status"],
            {
                "certificateArn": "arn:aws:acm:us-east-1:123456789012:certificate/mock-certificate-id",
                "certValidationRecordName": "_acmvalidation.static.trololo.demotw.com.",
                "certValidationRecordValue": "validate.acm-validations.aws.",
            },
        )
        self.assertNotIn("cert-validation-record", got["desired"]["resources"])
        self.assertNotIn("certificate-validation", got["desired"]["resources"])

    def test_composes_validation_record_and_validation_once_status_recorded(self) -> None:
        req = fnv1.RunFunctionRequest(
            observed=fnv1.State(
                composite=fnv1.Resource(
                    resource=resource.dict_to_struct(
                        {
                            "apiVersion": "platform.cia-infra-test.io/v1alpha1",
                            "kind": "DnsValidatedCertificate",
                            "spec": BASE_SPEC,
                            "status": {
                                "certificateArn": "arn:aws:acm:us-east-1:123456789012:certificate/mock-certificate-id",
                                "certValidationRecordName": "_acmvalidation.static.trololo.demotw.com.",
                                "certValidationRecordValue": "validate.acm-validations.aws.",
                            },
                        }
                    ),
                ),
            ),
        )

        got = self.run_compose(req)

        record = got["desired"]["resources"]["cert-validation-record"]["resource"]
        self.assertEqual(record["kind"], "Record")
        self.assertEqual(record["spec"]["forProvider"]["name"], "_acmvalidation.static.trololo.demotw.com.")
        self.assertEqual(record["spec"]["forProvider"]["records"], ["validate.acm-validations.aws."])
        self.assertEqual(record["spec"]["forProvider"]["zoneId"], "Z00921083AT1Z6WZY8LYW")

        validation = got["desired"]["resources"]["certificate-validation"]["resource"]
        self.assertEqual(validation["kind"], "CertificateValidation")
        self.assertEqual(
            validation["spec"]["forProvider"]["certificateArn"],
            "arn:aws:acm:us-east-1:123456789012:certificate/mock-certificate-id",
        )
        self.assertEqual(
            validation["spec"]["forProvider"]["validationRecordFqdns"],
            ["_acmvalidation.static.trololo.demotw.com."],
        )


if __name__ == "__main__":
    unittest.main()
