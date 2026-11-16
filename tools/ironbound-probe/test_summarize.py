import unittest
from summarize import summarize


class SummaryTests(unittest.TestCase):
    def test_service_connection_and_transport_do_not_claim_motor_samples(self):
        rows = [
            {"kind": "state", "received_elapsed_ms": 0, "value": 0},
            {"kind": "message", "received_elapsed_ms": 10, "value": {
                "msgtype": 4147, "body": {"component_type": 1, "bytes_received": 0, "serial_number": "PRIVATE"}}},
            {"kind": "capture_finished", "received_elapsed_ms": 20, "value": "duration_elapsed"},
        ]
        result = summarize(rows)
        self.assertTrue(result["complete"])
        self.assertEqual(result["motor_sample_count"], 0)
        self.assertIsNone(result["motor_arrival_gap_ms"])
        self.assertNotIn("PRIVATE", str(result))

    def test_unknown_messages_are_counted_without_exposing_private_payload(self):
        result = summarize([{"kind": "message", "received_elapsed_ms": 0, "value": {
            "msgtype": 9999, "body": {"user": "PRIVATE"}}}])
        self.assertEqual(result["message_counts"], {"9999": 1})
        self.assertFalse(result["complete"])
        self.assertNotIn("PRIVATE", str(result))

    def test_motor_arrival_timing_is_measured_not_assumed(self):
        rows = [{"kind": "message", "received_elapsed_ms": t,
                 "value": {"msgtype": 4132, "body": {}}} for t in (100, 120, 170)]
        result = summarize(rows)
        self.assertEqual(result["motor_sample_count"], 3)
        self.assertEqual(result["motor_arrival_gap_ms"], {"median": 35, "max": 50})


if __name__ == "__main__":
    unittest.main()
