import argparse
from pathlib import Path
import hashlib
import urllib.request

URL = "https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.ALL.list.v04r01.csv"
def main():
    parser=argparse.ArgumentParser(description="Download NOAA NCEI IBTrACS v04r01 best-track CSV")
    parser.add_argument("--output",default="data/raw/ibtracs.ALL.list.v04r01.csv")
    args=parser.parse_args()
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    print("Downloading official NOAA NCEI IBTrACS archive...")
    urllib.request.urlretrieve(URL,out)
    print(f"Saved {out} ({out.stat().st_size:,} bytes)")
    print("SHA-256:", hashlib.sha256(out.read_bytes()).hexdigest(), "(record this and the retrieval date in your research log)")
if __name__=="__main__": main()
