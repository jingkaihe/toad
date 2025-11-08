import asyncio
from time import monotonic


async def shell_read(
    reader: asyncio.StreamReader,
    buffer_size: int,
    max_buffer_duration: float,
) -> bytes:
    """Read data from a stream reader, with buffer logic to reduce the number of chunks.

    Args:
        reader: A reader instance.
        buffer_size: Maximum buffer size.
        max_buffer_duration: Maximum time in seconds to buffer data.

    Returns:
        Bytes read. May be empty on the last read.
    """
    data = await reader.read(buffer_size)
    if data:
        buffer_time = monotonic() + max_buffer_duration
        # Accumulate data for a short period of time, or until we have enough data
        # This can reduce the number of refreshes we need to do
        # Resulting in faster updates and less flicker.
        try:
            while len(data) < buffer_size and (time := monotonic()) < buffer_time:
                async with asyncio.timeout(buffer_time - time):
                    data += await reader.read(buffer_size)
        except asyncio.TimeoutError:
            pass
    return data
