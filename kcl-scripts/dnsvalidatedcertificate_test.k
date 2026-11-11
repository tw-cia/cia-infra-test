# kcl test ./... -- mirrors scripts/tests/test_dnsvalidatedcertificate.py and
# functions/dnsvalidatedcertificate/tests/test_fn.py, which exercise this
# same logic (and the other implementations) via `crossplane composition
# render` / direct fn invocation. This runs directly against
# composeCertificate() instead -- no Docker, no render.
import dnsvalidatedcertificate

dvcByName = lambda items: [{str:any}] -> {str:{str:any}} {
    {item["metadata"]["annotations"]["krm.kcl.dev/composition-resource-name"]: item for item in items if "metadata" in item}
}

dvcComposite = lambda items: [{str:any}] -> {str:any} {
    [item for item in items if not ("metadata" in item)][0]
}

DVC_BASE_SPEC = {
    "domainName": "static.trololo.demotw.com"
    "zone": {"id": "Z00921083AT1Z6WZY8LYW"}
}

dvcOxr = lambda spec: {str:any}, status: {str:any} -> {str:any} {
    {"spec": spec, "status": status}
}

test_composes_certificate_only_when_not_yet_observed = lambda {
    items = dnsvalidatedcertificate.composeCertificate(dvcOxr(DVC_BASE_SPEC, {}), {})
    byName = dvcByName(items)
    assert sorted([k for k in byName]) == ["certificate"]

    certificate = byName["certificate"].spec
    assert certificate.forProvider.region == "us-east-1"
    assert certificate.forProvider.validationMethod == "DNS"
    assert certificate.forProvider.domainName == "static.trololo.demotw.com"
    assert certificate.providerConfigRef == {"kind": "ClusterProviderConfig", "name": "pod-identity"}

    composite = dvcComposite(items)
    assert composite.status == {}
}

test_surfaces_status_but_not_validation_resources_once_certificate_observed = lambda {
    ocds = {
        "certificate": {
            "Resource": {
                "status": {
                    "atProvider": {
                        "arn": "arn:aws:acm:us-east-1:123456789012:certificate/mock-certificate-id"
                        "domainValidationOptions": [{
                            "resourceRecordName": "_acmvalidation.static.trololo.demotw.com."
                            "resourceRecordValue": "validate.acm-validations.aws."
                        }]
                    }
                }
            }
        }
    }
    items = dnsvalidatedcertificate.composeCertificate(dvcOxr(DVC_BASE_SPEC, {}), ocds)
    byName = dvcByName(items)
    assert not ("cert-validation-record" in byName)
    assert not ("certificate-validation" in byName)

    composite = dvcComposite(items)
    assert composite.status == {
        "certificateArn": "arn:aws:acm:us-east-1:123456789012:certificate/mock-certificate-id"
        "certValidationRecordName": "_acmvalidation.static.trololo.demotw.com."
        "certValidationRecordValue": "validate.acm-validations.aws."
    }
}

test_composes_validation_record_and_validation_once_status_recorded = lambda {
    status = {
        "certificateArn": "arn:aws:acm:us-east-1:123456789012:certificate/mock-certificate-id"
        "certValidationRecordName": "_acmvalidation.static.trololo.demotw.com."
        "certValidationRecordValue": "validate.acm-validations.aws."
    }
    items = dnsvalidatedcertificate.composeCertificate(dvcOxr(DVC_BASE_SPEC, status), {})
    byName = dvcByName(items)

    record = byName["cert-validation-record"].spec.forProvider
    assert record.name == "_acmvalidation.static.trololo.demotw.com."
    assert record.records == ["validate.acm-validations.aws."]
    assert record.zoneId == "Z00921083AT1Z6WZY8LYW"

    validation = byName["certificate-validation"].spec.forProvider
    assert validation.certificateArn == "arn:aws:acm:us-east-1:123456789012:certificate/mock-certificate-id"
    assert validation.validationRecordFqdns == ["_acmvalidation.static.trololo.demotw.com."]
}

test_certificate_validation_waits_on_the_record_it_created = lambda {
    # Not that each resource independently matches a hardcoded value (the
    # test above already covers that), but that CertificateValidation is
    # actually waiting on the exact FQDN the Record resource publishes, not
    # just a coincidentally-equal literal.
    status = {
        "certificateArn": "arn:aws:acm:us-east-1:123456789012:certificate/mock-certificate-id"
        "certValidationRecordName": "_acmvalidation.static.trololo.demotw.com."
        "certValidationRecordValue": "validate.acm-validations.aws."
    }
    items = dnsvalidatedcertificate.composeCertificate(dvcOxr(DVC_BASE_SPEC, status), {})
    byName = dvcByName(items)

    record = byName["cert-validation-record"].spec.forProvider
    validation = byName["certificate-validation"].spec.forProvider

    assert validation.validationRecordFqdns == [record.name]
}
