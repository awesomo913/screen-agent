#!/usr/bin/env python3
"""Auto System Cleaner - Screen-controlled system cleanup and optimization tool."""
import os,sys,time,json,argparse,shutil,subprocess,glob
from datetime import datetime,timedelta
from dataclasses import dataclass,field
from typing import List,Dict
from pathlib import Path
import pyautogui

@dataclass
class CleanupResult:
    category:str;files_removed:int=0;space_freed_mb:float=0;errors:List[str]=field(default_factory=list)

class SystemCleaner:
    TEMP_LOCATIONS=[os.environ.get("TEMP",""),os.environ.get("TMP",""),os.path.expanduser("~/AppData/Local/Temp"),os.path.expanduser("~/AppData/Local/Microsoft/Windows/INetCache"),"C:/Windows/Temp"]
    BROWSER_CACHES={"chrome":os.path.expanduser("~/AppData/Local/Google/Chrome/User Data/Default/Cache"),"edge":os.path.expanduser("~/AppData/Local/Microsoft/Edge/User Data/Default/Cache"),"firefox":os.path.expanduser("~/AppData/Local/Mozilla/Firefox/Profiles")}
    def __init__(self,config_path=None,log_dir=None):
        self.config_path=config_path or os.path.expanduser("~/.system_cleaner_config.json")
        self.log_dir=log_dir or os.path.expanduser("~/cleaner_logs")
        os.makedirs(self.log_dir,exist_ok=True)
        self.results:List[CleanupResult]=[]
    def scan_temp_files(self):
        total_size=0;total_files=0
        for loc in self.TEMP_LOCATIONS:
            if os.path.isdir(loc):
                for root,dirs,files in os.walk(loc):
                    for f in files:
                        try:
                            path=os.path.join(root,f)
                            total_size+=os.path.getsize(path);total_files+=1
                        except:pass
        print("Temp files: "+str(total_files)+" files, "+str(round(total_size/1024/1024,1))+" MB")
        return total_files,total_size
    def clean_temp_files(self,older_than_days=1):
        result=CleanupResult(category="temp_files")
        cutoff=datetime.now()-timedelta(days=older_than_days)
        for loc in self.TEMP_LOCATIONS:
            if not os.path.isdir(loc):continue
            for root,dirs,files in os.walk(loc,topdown=False):
                for f in files:
                    try:
                        path=os.path.join(root,f)
                        mtime=datetime.fromtimestamp(os.path.getmtime(path))
                        if mtime<cutoff:
                            size=os.path.getsize(path)
                            os.remove(path)
                            result.files_removed+=1;result.space_freed_mb+=size/1024/1024
                    except Exception as e:result.errors.append(str(e))
        self.results.append(result)
        print("Cleaned temp: "+str(result.files_removed)+" files, "+str(round(result.space_freed_mb,1))+" MB freed")
        return result
    def clean_recycle_bin(self):
        try:
            if sys.platform=="win32":
                import ctypes
                ctypes.windll.shell32.SHEmptyRecycleBinW(None,None,7)
                print("Recycle bin emptied")
            return True
        except:
            try:
                subprocess.run(["PowerShell","-Command","Clear-RecycleBin -Force"],capture_output=True)
                return True
            except:pass
        return False
    def clean_downloads(self,older_than_days=30,extensions=None):
        downloads=os.path.expanduser("~/Downloads")
        if not os.path.isdir(downloads):return
        result=CleanupResult(category="downloads")
        cutoff=datetime.now()-timedelta(days=older_than_days)
        exts=set(extensions) if extensions else None
        for f in os.listdir(downloads):
            path=os.path.join(downloads,f)
            if not os.path.isfile(path):continue
            try:
                mtime=datetime.fromtimestamp(os.path.getmtime(path))
                if mtime<cutoff:
                    if exts and Path(f).suffix.lower() not in exts:continue
                    size=os.path.getsize(path)
                    os.remove(path)
                    result.files_removed+=1;result.space_freed_mb+=size/1024/1024
            except Exception as e:result.errors.append(str(e))
        self.results.append(result)
        print("Cleaned downloads: "+str(result.files_removed)+" files, "+str(round(result.space_freed_mb,1))+" MB")
    def clean_thumbnails(self):
        thumb_path=os.path.expanduser("~/AppData/Local/Microsoft/Windows/Explorer")
        result=CleanupResult(category="thumbnails")
        if os.path.isdir(thumb_path):
            for f in os.listdir(thumb_path):
                if f.startswith("thumbcache"):
                    try:
                        path=os.path.join(thumb_path,f)
                        size=os.path.getsize(path)
                        os.remove(path)
                        result.files_removed+=1;result.space_freed_mb+=size/1024/1024
                    except:pass
        self.results.append(result)
        print("Cleaned thumbnails: "+str(result.files_removed)+" files")
    def run_disk_cleanup_ui(self):
        subprocess.Popen(["cleanmgr.exe"])
        time.sleep(3)
        print("Disk Cleanup opened - complete manually")
    def flush_dns(self):
        try:
            subprocess.run(["ipconfig","/flushdns"],capture_output=True);print("DNS cache flushed")
        except:print("DNS flush failed")
    def full_cleanup(self,older_than=1):
        print("=== Full System Cleanup ===")
        self.clean_temp_files(older_than)
        self.clean_thumbnails()
        self.flush_dns()
        total_freed=sum(r.space_freed_mb for r in self.results)
        total_files=sum(r.files_removed for r in self.results)
        print("\n=== Summary ===")
        print("Files removed: "+str(total_files))
        print("Space freed: "+str(round(total_freed,1))+" MB")
        self._save_log()
    def _save_log(self):
        log=os.path.join(self.log_dir,"cleanup_"+datetime.now().strftime("%Y%m%d_%H%M%S")+".json")
        data=[{"category":r.category,"files":r.files_removed,"freed_mb":round(r.space_freed_mb,1),"errors":len(r.errors)} for r in self.results]
        with open(log,"w") as f:json.dump(data,f,indent=2)

def main():
    parser=argparse.ArgumentParser(description="Auto System Cleaner")
    subparsers=parser.add_subparsers(dest="command")
    subparsers.add_parser("scan");subparsers.add_parser("clean-temp")
    subparsers.add_parser("clean-downloads");subparsers.add_parser("clean-thumbnails")
    subparsers.add_parser("flush-dns");subparsers.add_parser("disk-cleanup")
    full_p=subparsers.add_parser("full");full_p.add_argument("--older-than",type=int,default=1)
    args=parser.parse_args()
    cleaner=SystemCleaner()
    if args.command=="scan":cleaner.scan_temp_files()
    elif args.command=="clean-temp":cleaner.clean_temp_files()
    elif args.command=="clean-downloads":cleaner.clean_downloads()
    elif args.command=="clean-thumbnails":cleaner.clean_thumbnails()
    elif args.command=="flush-dns":cleaner.flush_dns()
    elif args.command=="disk-cleanup":cleaner.run_disk_cleanup_ui()
    elif args.command=="full":cleaner.full_cleanup(args.older_than)
    else:parser.print_help()

if __name__=="__main__":
    main()
