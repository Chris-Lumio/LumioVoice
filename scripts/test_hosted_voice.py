"""Generate one short real sample; downloads audio, never model weights."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import aiohttp
from config import Settings, PRIVATE
from services import Services

async def main():
    async with aiohttp.ClientSession() as session:
        audio = await Services(Settings(), session).synthesize('أهلين! شو بدّك نعمل هلّق؟')
        target = PRIVATE / 'voice-test.wav'
        target.write_bytes(audio)
        print(f'Hosted speech succeeded: {len(audio)} bytes saved to {target}')

asyncio.run(main())
