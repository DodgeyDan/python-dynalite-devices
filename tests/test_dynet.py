"""Tests for various packets in DynetPacket."""

import pytest

from dynalite_devices_lib.dynet import DynetPacket, PacketError

pytestmark = pytest.mark.asyncio


async def test_packet_lengths():
    """Test what happens when creating a packet of size not equal to 8."""
    packet = DynetPacket()
    packet.to_msg(3, 6, [1, 2, 3])
    with pytest.raises(PacketError):
        DynetPacket(packet.msg[0:7])
    with pytest.raises(PacketError):
        DynetPacket(packet.msg + bytearray([3]))
    DynetPacket(packet.msg[0:8])


async def test_channel_fade_limit():
    """Test that set_channel_level has a limit at 0xFF (5.1 seconds)."""
    packet1 = DynetPacket.set_channel_level_packet(1, 1, 1, 100)
    packet2 = DynetPacket.set_channel_level_packet(1, 1, 1, 5.101)
    packet3 = DynetPacket.set_channel_level_packet(1, 1, 1, 5.05)
    assert packet1.msg == packet2.msg
    assert packet1.msg != packet3.msg