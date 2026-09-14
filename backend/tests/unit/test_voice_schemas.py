from app.schemas.duplex.voice import VoiceConnectConfig

def test_connect_defaults():
    c = VoiceConnectConfig(case_number="MED-2026-001", participant_id="party_a")
    assert c.protocol_version == 2 and c.output_mode == "voice"
