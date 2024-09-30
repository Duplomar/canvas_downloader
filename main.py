import aiohttp
import argparse
import asyncio

queue = []

def download_page(base_url: str, url: str):
    pass

async def main():
    parser = argparse.ArgumentParser(
        prog='Canvas Downloader',
        description='Downloads all pages and files from the specified Canvas page',
    )
    parser.add_argument('base_url')
    parser.add_argument('entry_url')
    args = parser.parse_args()

    base_url = args.base_url
    queue.append(args.entry_url)

    while len(queue):
        download_page(base_url, queue.pop(0))

if __name__ == "__main__":
    asyncio.run(main())
