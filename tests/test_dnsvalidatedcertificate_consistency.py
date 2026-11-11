"""Proves that the Route53 validation record and the ACM CertificateValidation
resource are actually coupled to each other, for every implementation -- not
that each independently matches a hardcoded expected value (test_equivalence.py
and test_render.py already cover that), but that CertificateValidation is
waiting on the exact FQDN the Record resource actually publishes. If these
ever diverged, ACM would wait forever for a DNS record that doesn't match
what's actually there.

Shares test_equivalence.py's render harness (same requirements -- see that
file's docstring).
"""

import pytest

from test_equivalence import METHODS, find_one, render_method


@pytest.mark.parametrize("method", METHODS)
def test_dnsvalidatedcertificate_validation_waits_on_the_record_it_created(method):
    # The only scenario where both the validation Record and the
    # CertificateValidation resource render at once.
    xr = "tests/fixtures/dns-validated-certificate-xr-observed.yaml"
    docs = render_method(method, xr, "dnsvalidatedcertificate")

    record = find_one(docs, "Record")["spec"]["forProvider"]
    validation = find_one(docs, "CertificateValidation")["spec"]["forProvider"]

    assert validation["validationRecordFqdns"] == [record["name"]], (
        "CertificateValidation is waiting on a different FQDN than the Record it's supposed to validate against"
    )
