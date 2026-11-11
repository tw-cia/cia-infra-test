import unittest

from crossplane.function import logging, resource
from crossplane.function.proto.v1 import run_function_pb2 as fnv1
from google.protobuf import duration_pb2 as durationpb
from google.protobuf import json_format
from google.protobuf import struct_pb2 as structpb

from dnsvalidatedcertificate_function import fn

PROVIDER_CONFIG = {"kind": "ClusterProviderConfig", "name": "pod-identity"}

BASE_SPEC = {
    "domainName": "static.trololo.demotw.com",
    "zone": {"id": "Z00921083AT1Z6WZY8LYW"},
}


class TestFunctionRunner(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.maxDiff = 4000
        logging.configure(level=logging.Level.DISABLED)

    async def run_function(self, req: fnv1.RunFunctionRequest) -> dict:
        got = await fn.FunctionRunner().RunFunction(req, None)
        return json_format.MessageToDict(got)

    async def test_composes_certificate_only_when_not_yet_observed(self) -> None:
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

        got = await self.run_function(req)

        self.assertEqual(json_format.MessageToDict(want), got, "-want, +got")

    async def test_surfaces_status_but_not_validation_resources_once_certificate_observed(self) -> None:
        # One reconcile after the Certificate first exists: AWS has reported
        # back its ARN and validation record, but cert-validation-record and
        # certificate-validation can't render *this* pass -- same
        # two-pass limitation as the YAML version (see fn.py's docstring).
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

        got = await self.run_function(req)

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

    async def test_composes_validation_record_and_validation_once_status_recorded(self) -> None:
        # A later reconcile still: the composite's own status already has
        # what the previous pass surfaced, so the gated resources can now
        # render.
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

        got = await self.run_function(req)

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

    async def test_certificate_validation_waits_on_the_record_it_created(self) -> None:
        # Mirrors tests/test_dnsvalidatedcertificate_consistency.py -- not
        # that each resource independently matches a hardcoded value (the
        # test above already covers that), but that CertificateValidation is
        # actually waiting on the exact FQDN the Record resource publishes,
        # not just a coincidentally-equal literal.
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

        got = await self.run_function(req)

        record = got["desired"]["resources"]["cert-validation-record"]["resource"]["spec"]["forProvider"]
        validation = got["desired"]["resources"]["certificate-validation"]["resource"]["spec"]["forProvider"]

        self.assertEqual(
            validation["validationRecordFqdns"],
            [record["name"]],
            "CertificateValidation is waiting on a different FQDN than the Record it's supposed to validate against",
        )


if __name__ == "__main__":
    unittest.main()
