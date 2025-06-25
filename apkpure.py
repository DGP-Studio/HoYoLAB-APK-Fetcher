# -*- coding: utf-8 -*-
"""
Fetch latest HoYoLAB XAPK info from APKPure, cache version/size locally,
and download the file only if the version is new.
"""

from __future__ import annotations

import json
from pathlib import Path

import cloudscraper
from bs4 import BeautifulSoup


PAGE_URL = "https://apkpure.com/hoyolab/com.mihoyo.hoyolab/download"
DOWNLOAD_URL = "https://d.apkpure.com/b/XAPK/com.mihoyo.hoyolab?version=latest"
CACHE_FILE = Path("cache.json")
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://apkpure.com/",
    "Connection": "keep-alive",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "DNT": "1",
}

COOKIES: dict[str, str] = {
    # "cf_clearance": "your_cf_clearance_cookie",
    # "sessionid": "your_session_id",
}


def get_latest_version_and_size() -> tuple[str, float]:
    """
    访问下载页，解析得到最新版本号和文件大小（MB）
    """
    scraper = cloudscraper.create_scraper()
    response = scraper.get(PAGE_URL, headers=HEADERS, cookies=COOKIES, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # 优先读取 <body> 的 data-dt-* 属性
    body = soup.find("body", attrs={"data-dt-version": True, "data-dt-filesize": True})
    if body:
        version = body["data-dt-version"].strip()
        size_mb = round(int(body["data-dt-filesize"]) / 1024 / 1024, 1)
        return version, size_mb

    ver_tag = soup.select_one(".version-box .version-name")
    desc_li = soup.select_one(
        'ul.dev-partnership-head-info li div.desc:contains("Size")'
    )
    if ver_tag and desc_li:
        version = ver_tag.get_text(strip=True)
        size_text = (
            desc_li.find_previous_sibling("div", class_="head")
            .get_text(strip=True)
            .lower()
        )
        size_mb = float(size_text.split()[0])
        return version, size_mb

    raise RuntimeError("无法解析最新版本号或文件大小")


def load_cache() -> dict[str, float]:
    """读取本地 cache.json，没有则返回空字典"""
    if not CACHE_FILE.exists():
        return {}
    with CACHE_FILE.open(encoding="utf-8") as fp:
        return json.load(fp)


def save_cache(cache: dict[str, float]) -> None:
    with CACHE_FILE.open("w", encoding="utf-8") as fp:
        json.dump(cache, fp, indent=2, ensure_ascii=False)


def download_apk(version: str, size_mb: float) -> None:
    """
    流式方式下载 XAPK
    """
    output_file = Path(f"hoyolab.xapk")
    if output_file.exists():
        print(f"[!] 文件 {output_file} 已存在，跳过下载。")
        return

    with open("./latest", "w+", encoding="utf-8") as f:
        f.write(version)

    scraper = cloudscraper.create_scraper()
    with scraper.get(DOWNLOAD_URL, headers=HEADERS, cookies=COOKIES, stream=True) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0)) or int(size_mb * 1024 * 1024)
        chunk_size = 8192
        downloaded = 0

        print(f"[+] 开始下载 {output_file}  (≈ {size_mb:.1f} MB)")
        with output_file.open("wb") as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    percent = downloaded * 100 / total
                    print(
                        f"\r    已下载: {downloaded / 1024 / 1024:.2f} MB "
                        f"({percent:.2f}%)",
                        end="",
                        flush=True,
                    )
    print("\n[√] 下载完成")


def main() -> None:
    version, size_mb = get_latest_version_and_size()
    print(f"[i] 最新版本: {version}  |  大小: {size_mb:.1f} MB")

    Path("latest").write_text(version, encoding="utf-8")
    cache = load_cache()
    if version in cache:
        print("[✓] 该版本已记录在 cache.json，无需下载。程序结束。")
        return

    cache[version] = size_mb
    save_cache(cache)
    print("[+] 已将新版本写入 cache.json")

    download_apk(version, size_mb)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[×] 发生错误: {exc}")
