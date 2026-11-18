import tempfile
import unittest
from cost_review.core import ingest, detect_spikes, parse_tags


class CostTests(unittest.TestCase):
    def write(self, text):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
        f.write(text)
        f.close()
        return f.name

    def test_ingest_aliases_and_tags(self):
        name = self.write("provider_service,billing_date,amount,labels\ncompute,2026-01-01,12.50,\"{\"\"team\"\":\"\"platform\"\"}\"\n")
        rows, errors = ingest(name)
        self.assertEqual(errors, [])
        self.assertEqual(rows[0]["service"], "compute")
        self.assertEqual(rows[0]["cost"], 12.5)
        self.assertEqual(rows[0]["tags"], {"team": "platform"})

    def test_spike_and_zero_mad(self):
        rows = [{"service":"s","day":f"2026-01-{i:02d}","cost":100.0 if i < 8 else 1000.0,"tags":{}} for i in range(1, 10)]
        findings = detect_spikes(rows, mad_threshold=3)
        spike = next(x for x in findings if x["day"] == "2026-01-09")
        self.assertEqual(spike["status"], "review_candidate")
        self.assertIn("Review allocation", spike["action"])

    def test_insufficient_history(self):
        rows = [{"service":"s","day":"2026-01-01","cost":10,"tags":{}}]
        findings = detect_spikes(rows)
        self.assertEqual(findings[0]["status"], "insufficient_history")

    def test_bad_rows_and_negative(self):
        name = self.write("service,day,cost\nok,2026-01-01,12\nbad,not-a-date,12\nneg,2026-01-01,-1\nnonnum,2026-01-01,abc\n")
        rows, errors = ingest(name)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(errors), 3)

    def test_tag_formats(self):
        self.assertEqual(parse_tags("team=platform;env=prod"), {"team":"platform","env":"prod"})
        self.assertEqual(parse_tags('{"team":"platform"}'), {"team":"platform"})

    def test_bad_threshold(self):
        with self.assertRaises(ValueError):
            detect_spikes([], mad_threshold=0)


if __name__ == "__main__":
    unittest.main()
