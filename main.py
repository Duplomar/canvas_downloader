import aiohttp
import argparse
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlsplit, SplitResult
import re
from pathlib import Path

BASE_LOCATION = ""
DIR_ROOT = Path("./canvas_content").resolve()

queue = asyncio.Queue()
seen = set()
busy = []


def get_location(url: str):
    return url.split("://", 1)[1]


async def download_page(session: aiohttp.ClientSession, url: str) -> list[str]:
    """
    Downloads and saves the content of the url. Returns relevant urls to look up
    """
    async with session.head(url) as response:
        content_type = response.headers.get("content-type", None)

    if content_type:
        is_html = "text/html" in content_type.split(";")

        location = get_location(url)
        if location.startswith(BASE_LOCATION):

            save_path = (DIR_ROOT / "internal_content") / location[len(BASE_LOCATION):]
            save_path = save_path.resolve()

            # Assert save path is within the folder specified
            if not save_path.is_relative_to(DIR_ROOT / "internal_content"):
                return []

            if is_html:
                    async with session.get(url) as response:
                        text = await response.text()
                        soup = BeautifulSoup(text, 'lxml')
                        relevant_urls = []
                        for tag in soup.find_all():
                            val = None
                            if tag.name in ["audio", "embed", "img", "input", "script", "source", "track", "video"]:
                                val = tag.get("src", None)
                            elif tag.name in ["a", "link", "area"]:
                                val = tag.get("href", None)

                            if val:
                                relevant_urls.append(val)

                        print("downloading page", url, "to", save_path.as_posix())

                        return relevant_urls

            else:
                print("downloading content", url)

        elif not is_html:
            
            save_path = DIR_ROOT / "external_content"
            print("Downloading external content", url)

    return []


def clean_url(ref_url: str, url: str) -> str:
    fields = urlsplit(urljoin(ref_url, url))._asdict() # convert to absolute URLs and split
    fields['path'] = re.sub(r'/$', '', fields['path']) # remove trailing /
    fields['fragment'] = '' # remove targets within a page
    fields = SplitResult(**fields)
    return fields.geturl()


async def worker(id: int, session: aiohttp.ClientSession):
    global busy
    while any(busy) or queue.qsize():
        if queue.qsize():
            url, max_depth = await queue.get()
            location = get_location(url)
            if max_depth <=0 or location in seen:
                continue

            seen.add(location)

            busy[id] = True
            res = await download_page(session, url)
            clean_urls = map(lambda link: clean_url(url, link), res)
            for sub_url in clean_urls:
                if sub_url.startswith("http") and max_depth - 1:
                    await queue.put((sub_url, max_depth - 1))
                        
            
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
    parser.add_argument('-m', "--max_depth", default=2)
    args = parser.parse_args()

    global BASE_LOCATION, busy
    BASE_LOCATION = get_location(args.base_url)
    await queue.put((args.entry_url, args.max_depth))
    seen.add(args.entry_url)
    busy.extend([False] * args.n)
    
    async with aiohttp.ClientSession() as session:
        await asyncio.gather(*[worker(i, session) for i in range(args.n)])


if __name__ == "__main__":
    asyncio.run(main())
    print(seen)
