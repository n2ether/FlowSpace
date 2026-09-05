"""Unit tests for Stripe → lead matching (no live server)."""
from fulfillment import checkout_lead_lookups, should_auto_start_automation


class TestCheckoutLeadLookups:
    def test_prefers_transaction_then_metadata_then_email(self):
        lookups = checkout_lead_lookups(
            metadata={"lead_id": "meta-1", "email": "Ada@Example.com"},
            customer_email="ada@example.com",
            transaction_lead_id="tx-1",
        )
        reasons = [r for r, _ in lookups]
        assert reasons == ["transaction.lead_id", "metadata.lead_id", "email"]
        assert lookups[0][1] == {"id": "tx-1"}
        assert lookups[1][1] == {"id": "meta-1"}
        email_q = lookups[2][1]
        assert email_q["email"]["$options"] == "i"
        assert email_q["email"]["$regex"].lower() == r"^ada@example\.com$"

    def test_leadId_camel_case_alias(self):
        lookups = checkout_lead_lookups(metadata={"leadId": "abc"})
        assert lookups[0] == ("metadata.lead_id", {"id": "abc"})

    def test_skips_duplicate_ids(self):
        lookups = checkout_lead_lookups(
            metadata={"lead_id": "same"},
            transaction_lead_id="same",
        )
        ids = [q["id"] for _, q in lookups if "id" in q]
        assert ids == ["same"]

    def test_empty_inputs_yield_no_lookups(self):
        assert checkout_lead_lookups() == []


class TestShouldAutoStart:
    def test_blocks_in_flight_and_delivered(self):
        assert should_auto_start_automation("processing") is False
        assert should_auto_start_automation("delivered") is False

    def test_allows_retryable(self):
        for status in ("new", "paid", "pdf_ready", "error", None):
            assert should_auto_start_automation(status) is True
