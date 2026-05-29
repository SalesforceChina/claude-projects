"""
fetch_data.py — 用 akshare 拉取股票数据，存入 data/ 目录
用法：
    python fetch_data.py                     # 拉取 watchlist.md 中所有股票
    python fetch_data.py 600519              # 拉取单只股票
    python fetch_data.py 600519 000858       # 拉取多只股票

依赖：pip install akshare pandas
"""

import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime, timedelta

import akshare as ak
import pandas as pd

# Windows GBK 终端输出兼容
if sys.stdout.encoding and sys.stdout.encoding.lower() in ("gbk", "cp936"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── 路径配置 ──────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
WATCHLIST_FILE = BASE_DIR / "watchlist" / "watchlist.md"
DATA_DIR.mkdir(exist_ok=True)

# ── 日期范围（默认近 2 年）────────────────────────────────
END_DATE = datetime.today().strftime("%Y%m%d")
START_DATE = (datetime.today() - timedelta(days=730)).strftime("%Y%m%d")


def parse_watchlist() -> list[str]:
    """从 watchlist.md 解析股票代码（6位数字开头的行）"""
    if not WATCHLIST_FILE.exists():
        return []
    codes = []
    for line in WATCHLIST_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip().lstrip("-| ").strip()
        if line[:6].isdigit():
            codes.append(line[:6])
    return codes


def fetch_hist(code: str, retries: int = 3) -> pd.DataFrame:
    """拉取日线历史（前复权）：优先新浪，备用东财"""
    # 新浪接口：sh前缀沪市，sz前缀深市
    prefix = "sh" if code.startswith("6") else "sz"
    for i in range(retries):
        try:
            df = ak.stock_zh_a_daily(
                symbol=f"{prefix}{code}",
                start_date=START_DATE,
                end_date=END_DATE,
                adjust="qfq",
            )
            return df
        except Exception:
            if i < retries - 1:
                time.sleep(2)

    # 备用东财接口
    for i in range(retries):
        try:
            return ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=START_DATE,
                end_date=END_DATE,
                adjust="qfq",
            )
        except Exception as e:
            if i < retries - 1:
                time.sleep(2)
            else:
                raise


def fetch_info(code: str) -> dict:
    """拉取个股基本信息"""
    try:
        df = ak.stock_individual_info_em(symbol=code)
        return dict(zip(df["item"], df["value"]))
    except Exception:
        return {}


def fetch_financial(code: str) -> pd.DataFrame:
    """拉取主要财务指标"""
    try:
        return ak.stock_financial_abstract_ths(symbol=code, indicator="按年度")
    except Exception:
        return pd.DataFrame()


def save(code: str):
    print(f"[{code}] 正在拉取数据...")
    out_dir = DATA_DIR / code
    out_dir.mkdir(exist_ok=True)

    # 1. 日线数据
    try:
        hist = fetch_hist(code)
        hist.to_csv(out_dir / "hist.csv", index=False, encoding="utf-8-sig")
        print(f"  ✅ 日线数据 {len(hist)} 条 → data/{code}/hist.csv")
    except Exception as e:
        print(f"  ❌ 日线数据失败: {e}")

    # 2. 基本信息
    try:
        info = fetch_info(code)
        with open(out_dir / "info.json", "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
        print(f"  ✅ 基本信息 → data/{code}/info.json")
    except Exception as e:
        print(f"  ❌ 基本信息失败: {e}")

    # 3. 财务数据
    try:
        fin = fetch_financial(code)
        if not fin.empty:
            fin.to_csv(out_dir / "financial.csv", index=False, encoding="utf-8-sig")
            print(f"  ✅ 财务数据 {len(fin)} 期 → data/{code}/financial.csv")
    except Exception as e:
        print(f"  ❌ 财务数据失败: {e}")

    print(f"[{code}] 完成\n")


def main():
    codes = sys.argv[1:] if len(sys.argv) > 1 else parse_watchlist()

    if not codes:
        print("未指定股票代码，且 watchlist.md 为空。")
        print("用法：python fetch_data.py 600519")
        return

    print(f"共 {len(codes)} 只股票：{', '.join(codes)}")
    print(f"日期范围：{START_DATE} ~ {END_DATE}\n")

    for code in codes:
        save(code)

    print("=" * 40)
    print("全部完成！数据存储在 data/ 目录。")
    print("现在可以在 Cowork 中输入 /analyze [代码] 开始分析。")


if __name__ == "__main__":
    main()
