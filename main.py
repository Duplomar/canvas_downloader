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

def url_to_filename(url: str):
    location = get_location(url)

    return "".join(c for c in location if c.isalpha() or c.isdigit() or c==' ').rstrip()


async def get_save_directory(session: aiohttp.ClientSession, url: str) -> Path | None:
    """
    Gets the save directory for the given url. Returns None if the url should not be saved
    """

    save_path = None
    async with session.head(url) as response:
        content_type = response.headers.get("content-type", None)

    if not content_type:
        return None
    content_type = content_type.split(";")[0]
    
    is_html = "text/html" == content_type

    location = get_location(url)
    if location.startswith(BASE_LOCATION):

        save_path = (DIR_ROOT / "internal_content") / location[len(BASE_LOCATION):]
        save_path = save_path.resolve()
        # Assert save path is within the folder specified
        if not save_path.is_relative_to(DIR_ROOT / "internal_content"):
            return None
        
        if is_html:
            save_path = save_path.parent / (save_path.name + ".html")
            
    elif not is_html:
        if Path(url).suffix:
            suffix = Path(url).suffix
        else:
            suffix = "." + content_type.split("/")[1]

        save_path = (DIR_ROOT / "external_content") / (url_to_filename(url) + suffix)

    return save_path


async def get_urls_on_page(session: aiohttp.ClientSession, text: str, url: str) -> list[tuple[str, Path]]:
    soup = BeautifulSoup(text, 'lxml')
    relevant_urls: set[tuple[str, Path]] = set()
    for tag in soup.find_all():
        found_url: str|None = None
        if tag.name in ["audio", "embed", "img", "input", "script", "source", "track", "video"]:
            found_url = tag.get("src", None)
        elif tag.name in ["a", "link", "area"]:
            found_url = tag.get("href", None)

        if found_url and found_url.startswith("http"):
            found_url = clean_url(url, found_url)
            if found_url not in relevant_urls:
                found_url_save_path = await get_save_directory(session, found_url)
                if found_url_save_path:
                    relevant_urls.add((clean_url(url, found_url), found_url_save_path))

    return list(relevant_urls)


async def download_page(session: aiohttp.ClientSession, url: str, save_path: Path) -> list[tuple[str, Path]]:
    """
    Downloads and saves the content of the url. Returns relevant urls to look up
    """
    print("downloading page", url, "to", save_path.as_posix())
    async with session.get(url) as response:
        content_type = response.headers.get("content-type", None)

        if not content_type:
            return []
        content_type = content_type.split(";")[0]

        if content_type == "text/html": 
            text = await response.text()
            relevant_urls = await get_urls_on_page(session, text, url)

            for found_url, found_url_save_path in relevant_urls:
                text = text.replace(found_url, found_url_save_path.as_posix())

            with open("test.html", "w") as f:
                f.write(text)
            exit()
            return relevant_urls

        else:
            print("Downloading data:", url)
            data = await response.read()
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
            url, save_path, max_depth = await queue.get()
            location = get_location(url)
            if max_depth <=0 or location in seen:
                continue

            seen.add(location)

            busy[id] = True
            res = await download_page(session, url, save_path)
            for sub_url, sub_url_save_path in res:
                if sub_url.startswith("http") and max_depth - 1:
                    await queue.put((sub_url, sub_url_save_path, max_depth - 1))
                        
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
    await queue.put((
        args.entry_url, 
        (DIR_ROOT / "internal_content") / get_location(args.entry_url)[len(BASE_LOCATION):], 
        args.max_depth
    ))
    seen.add(args.entry_url)
    busy.extend([False] * args.n)
    
    async with aiohttp.ClientSession() as session:
        await asyncio.gather(*[worker(i, session) for i in range(args.n)])


if __name__ == "__main__":
    asyncio.run(main())
    print(seen)
