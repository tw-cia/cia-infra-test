from crossplane.function import resource
from google.protobuf.json_format import MessageToDict

PROVIDER_CONFIG = {"kind": "ClusterProviderConfig", "name": "pod-identity"}

def compose(req, rsp):
    xr = MessageToDict(req.observed.composite.resource)
    spec = xr["spec"]
    status_in = xr.get("status", {})
    domain_name = spec["domainName"]
    zone_id = spec["zone"]["id"]

    resource.update(
        rsp.desired.resources["certificate"],
        {
            "apiVersion": "acm.aws.m.upbound.io/v1beta1",
            "kind": "Certificate",
            "spec": {
                "forProvider": {
                    "region": "us-east-1",
                    "validationMethod": "DNS",
                    "domainName": domain_name,
                },
                "providerConfigRef": PROVIDER_CONFIG,
            },
        },
    )

    # Surface whatever the observed Certificate reports now, for the
    # *next* reconcile to use -- this pass's own gated resources
    # below only ever read status_in (the composite's status as it
    # already was coming in).
    status = {}
    if "certificate" in req.observed.resources:
        observed_certificate = MessageToDict(
            req.observed.resources["certificate"].resource
        )
        at_provider = observed_certificate.get("status", {}).get("atProvider", {})
        if at_provider.get("arn"):
            status["certificateArn"] = at_provider["arn"]
        validation_options = at_provider.get("domainValidationOptions") or []
        if validation_options:
            if validation_options[0].get("resourceRecordName"):
                status["certValidationRecordName"] = validation_options[0][
                    "resourceRecordName"
                ]
            if validation_options[0].get("resourceRecordValue"):
                status["certValidationRecordValue"] = validation_options[0][
                    "resourceRecordValue"
                ]
    if status:
        rsp.desired.composite.resource.update({"status": status})

    validation_record_name = status_in.get("certValidationRecordName")
    validation_record_value = status_in.get("certValidationRecordValue")
    if validation_record_name and validation_record_value:
        resource.update(
            rsp.desired.resources["cert-validation-record"],
            {
                "apiVersion": "route53.aws.m.upbound.io/v1beta1",
                "kind": "Record",
                "spec": {
                    "forProvider": {
                        "type": "CNAME",
                        "ttl": 300,
                        "name": validation_record_name,
                        "records": [validation_record_value],
                        "zoneId": zone_id,
                    },
                    "providerConfigRef": PROVIDER_CONFIG,
                },
            },
        )

    certificate_arn = status_in.get("certificateArn")
    if certificate_arn and validation_record_name:
        resource.update(
            rsp.desired.resources["certificate-validation"],
            {
                "apiVersion": "acm.aws.m.upbound.io/v1beta1",
                "kind": "CertificateValidation",
                "spec": {
                    "forProvider": {
                        "region": "us-east-1",
                        "certificateArn": certificate_arn,
                        "validationRecordFqdns": [validation_record_name],
                    },
                    "providerConfigRef": PROVIDER_CONFIG,
                },
            },
        )
