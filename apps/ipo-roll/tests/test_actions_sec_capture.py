"""Capture isolation and encrypted evidence transport; synthetic sources only."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import actions_sec_capture as m


REQUEST = dict(version='sec-capture-request/1', request_id='synthetic', filings=[
    dict(cik='0000000001', accession='0000000001-26-000001')])


class ActionsCaptureTests(unittest.TestCase):
    def test_request_rejects_unbounded_duplicate_and_arbitrary_targets(self):
        self.assertEqual(m.validate_request(REQUEST), REQUEST['filings'])
        variants = []
        for key, value in [('filings', []), ('filings', REQUEST['filings'] * 5),
                           ('filings', REQUEST['filings'] * 2), ('request_id', '../bad')]:
            variants.append(dict(REQUEST, **{key: value}))
        for key, value in [('cik', '1'), ('accession', '../../other'), ('url', 'https://evil.invalid')]:
            bad = copy.deepcopy(REQUEST); bad['filings'][0][key] = value; variants.append(bad)
        for bad in variants:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                m.validate_request(bad)

    def test_capture_uses_existing_contact_validation(self):
        with patch.dict('os.environ', {'SEC_EDGAR_USER_AGENT': ''}):
            with self.assertRaisesRegex(ValueError, 'SEC_EDGAR_USER_AGENT'):
                m.BoundedArchive('/unused')

    def test_roundtrip_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp); source = d/'source'; source.mkdir()
            (source/'source.htm').write_bytes(b'<html>Unreviewed source, never public</html>')
            key, cert = d/'key.pem', d/'cert.pem'
            subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes',
                            '-keyout',str(key),'-out',str(cert),'-days','1','-subj','/CN=Synthetic'],
                           check=True, capture_output=True)
            encrypted, restored = d/'evidence.cms', d/'restored.tar.gz'
            m.seal(source, cert, encrypted)
            decrypt = ['openssl','cms','-decrypt','-binary','-inform','DER',
                       '-in',str(encrypted),'-inkey',str(key),'-out',str(restored)]
            subprocess.run(decrypt, check=True, capture_output=True)
            with tarfile.open(restored) as archive:
                self.assertEqual(archive.extractfile('evidence/source.htm').read(),
                                 (source/'source.htm').read_bytes())
            raw = bytearray(encrypted.read_bytes()); raw[-1] ^= 1; encrypted.write_bytes(raw)
            self.assertNotEqual(subprocess.run(decrypt, capture_output=True).returncode, 0)

    def test_workflow_is_branch_scoped_and_uploads_only_ciphertext(self):
        workflow = (Path(__file__).parents[3]/'.github/workflows/ipo-roll-sec-capture.yml').read_text()
        self.assertIn('branches: [ipo-roll/foundation]', workflow)
        self.assertIn('secrets.SEC_EDGAR_USER_AGENT', workflow)
        self.assertIn('persist-credentials: false', workflow)
        self.assertIn('contents: read', workflow)
        self.assertIn('cancel-in-progress: false', workflow)
        self.assertEqual(workflow.count('uses: actions/upload-artifact'), 1)
        self.assertIn('path: ${{ runner.temp }}/ipo-roll-sec-capture/evidence.cms', workflow)
        for forbidden in ('schedule:', 'pull_request_target:', 'contents: write',
                          'SUPABASE', 'secrets.GITHUB_TOKEN'):
            self.assertNotIn(forbidden, workflow)
