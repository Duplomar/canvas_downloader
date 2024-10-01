import aiohttp
import argparse
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlsplit, SplitResult
import re

BASE_URL = ""

queue = asyncio.Queue()
seen = set()
busy = []


async def get_page_urls(session: aiohttp.ClientSession, url: str) -> list[str]:
    async with session.get(url) as response:
        text = await response.text()
        soup = BeautifulSoup(text, 'lxml')
        return [link.get('href') for link in soup.findAll("a")]


def clean_url(ref_url: str, url: str):
    fields = urlsplit(urljoin(ref_url, url))._asdict() # convert to absolute URLs and split
    fields['path'] = re.sub(r'/$', '', fields['path']) # remove trailing /
    fields['fragment'] = '' # remove targets within a page
    fields = SplitResult(**fields)

    if fields.scheme == 'http':
        httpurl = cleanurl = fields.geturl()
        httpsurl = httpurl.replace('http:', 'https:', 1)
    else:
        httpsurl = cleanurl = fields.geturl()
        httpurl = httpsurl.replace('https:', 'http:', 1)
    return cleanurl


async def worker(id: int, session: aiohttp.ClientSession):
    global busy
    while any(busy) or queue.qsize():
        if queue.qsize():
            url = await queue.get()
            busy[id] = True
            res = await get_page_urls(session, url)
            clean_urls = map(lambda link: clean_url(url, link), res)
            print(*clean_urls)
            
        else:
            busy[id] = False
            await asyncio.sleep(0.5)


async def main():
    parser = argparse.ArgumentParser(
        prog='Canvas Downloader',
        description='Downloads all pages and files from the specified Canvas page',
    )
    parser.add_argument('base_url')
    parser.add_argument('entry_url')
    parser.add_argument('--n', default=10)
    args = parser.parse_args()

    global BASE_URL, busy
    BASE_URL = args.base_url
    await queue.put(args.entry_url)
    seen.add(args.entry_url)
    busy.extend([False] * args.n)
    
    async with aiohttp.ClientSession() as session:
        await asyncio.gather(*[worker(i, session) for i in range(args.n)])

if __name__ == "__main__":
    asyncio.run(main())
