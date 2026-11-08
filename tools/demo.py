#!/usr/bin/env python3
"""Exercise the queue offline in a disposable directory. Makes no platform requests."""
import json
import struct
import sys
import tempfile
import zlib
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agent


def chunk(kind, data):
    return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data) & 0xffffffff)


def fixture_png():
    # A small, valid RGB PNG. It is used only to test local queue identity.
    raw = b''.join(b'\x00' + bytes((245, 240, 230)) * 16 for _ in range(16))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!IIBBBBB', 16, 16, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def main():
    with tempfile.TemporaryDirectory(prefix='instagram-agent-demo-') as directory:
        root = Path(directory)
        initialized = agent.initialize(root, 'demo_account')
        assert initialized['publishing_enabled'] is False
        cfg = agent.configuration(root)
        cfg.update(publishing_enabled=True, production_content_ready=True)
        (root / 'config.json').write_text(json.dumps(cfg))
        (root / 'fixture.png').write_bytes(fixture_png())
        manifest = {'account': 'demo_account', 'caption': 'Offline queue demonstration only.',
                    'assets': ['fixture.png'], 'kind': 'production', 'ready': True,
                    'scheduled_at': datetime.now(timezone.utc).isoformat(), 'slot': 'daily'}
        manifest_path = root / 'post.json'
        manifest_path.write_text(json.dumps(manifest))
        identifier = agent.enqueue(root, manifest_path)['id']
        assert agent.tick(root)['post_id'] == identifier
        assert agent.claim(root, identifier)['status'] == 'PUBLISHING'
        assert agent.check(root, identifier)['gate'] == 'PASS'
        agent.uncertain(root, identifier)
        blocked = False
        try:
            agent.claim(root, identifier)
        except ValueError as error:
            blocked = 'reconcile' in str(error)
        assert blocked
        print(json.dumps({'mode': 'offline_demo', 'platform_requests': 0,
                          'real_posts_published': 0, 'queue_and_final_gate': 'PASS',
                          'uncertain_outcome': 'VERIFY_REQUIRED', 'retry_blocked': blocked,
                          'temporary_state_removed_on_exit': True}, indent=2))


if __name__ == '__main__':
    main()
