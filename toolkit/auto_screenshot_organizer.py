#!/usr/bin/env python3
"""Auto Screenshot Organizer - Organize screenshots by content using OCR and image analysis."""
import os,sys,time,json,argparse,shutil,hashlib,re
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass,field
from typing import List,Dict
import pyautogui
from PIL import Image
try:
    import pytesseract;HAS_TESSERACT=True
except ImportError:HAS_TESSERACT=False

@dataclass
class ScreenshotInfo:
    path:str;filename:str;text_content:str="";category:str="uncategorized"
    timestamp:str="";width:int=0;height:int=0;hash:str=""

class ScreenshotOrganizer:
    CATEGORIES={"browser":["chrome","firefox","edge","safari","http","www","google","bing"],"code":["def ","class ","import ","function","const ","var ","return","print(","console."],"chat":["message","sent","received","typing","online"],"email":["inbox","sent","draft","compose","subject","from:","to:"],"document":["page","paragraph","word","excel","powerpoint"],"terminal":["$",">>>","C:\\","/usr/","sudo","npm","pip","git"],"settings":["settings","preferences","configuration","options","control panel"],"social":["like","share","comment","follow","post","tweet","story"]}
    def __init__(self,source_dir=None,output_dir=None):
        self.source_dir=source_dir or os.path.expanduser("~/Pictures/Screenshots")
        self.output_dir=output_dir or os.path.expanduser("~/OrganizedScreenshots")
        os.makedirs(self.output_dir,exist_ok=True)
        self.screenshots:List[ScreenshotInfo]=[]
    def scan_directory(self,directory=None):
        directory=directory or self.source_dir
        exts={".png",".jpg",".jpeg",".bmp",".gif"}
        files=sorted(f for f in Path(directory).rglob("*") if f.suffix.lower() in exts)
        print("Found "+str(len(files))+" screenshots")
        for fpath in files:
            img=Image.open(str(fpath))
            w,h=img.size
            with open(str(fpath),"rb") as f:file_hash=hashlib.md5(f.read(4096)).hexdigest()
            text=""
            if HAS_TESSERACT:
                try:text=pytesseract.image_to_string(img).strip()[:500]
                except:pass
            category=self._categorize(text,str(fpath))
            info=ScreenshotInfo(path=str(fpath),filename=fpath.name,text_content=text[:200],category=category,timestamp=datetime.fromtimestamp(fpath.stat().st_mtime).isoformat(),width=w,height=h,hash=file_hash)
            self.screenshots.append(info)
        return self.screenshots
    def _categorize(self,text,path):
        text_lower=text.lower()+" "+os.path.basename(path).lower()
        scores={}
        for cat,keywords in self.CATEGORIES.items():
            score=sum(1 for kw in keywords if kw.lower() in text_lower)
            if score>0:scores[cat]=score
        if scores:return max(scores,key=scores.get)
        return "uncategorized"
    def organize(self,copy=True):
        if not self.screenshots:self.scan_directory()
        counts={}
        for ss in self.screenshots:
            cat_dir=os.path.join(self.output_dir,ss.category)
            os.makedirs(cat_dir,exist_ok=True)
            dest=os.path.join(cat_dir,ss.filename)
            if not os.path.exists(dest):
                if copy:shutil.copy2(ss.path,dest)
                else:shutil.move(ss.path,dest)
            counts[ss.category]=counts.get(ss.category,0)+1
        print("Organized "+str(len(self.screenshots))+" screenshots:")
        for cat,count in sorted(counts.items()):print("  "+cat+": "+str(count))
    def find_duplicates(self):
        hashes={}
        for ss in self.screenshots:
            if ss.hash in hashes:hashes[ss.hash].append(ss.path)
            else:hashes[ss.hash]=[ss.path]
        dupes={h:paths for h,paths in hashes.items() if len(paths)>1}
        if dupes:
            print("Found "+str(len(dupes))+" duplicate groups:")
            for h,paths in dupes.items():
                print("  Hash "+h[:8]+":")
                for p in paths:print("    "+p)
        return dupes
    def search(self,query):
        return [ss for ss in self.screenshots if query.lower() in ss.text_content.lower() or query.lower() in ss.filename.lower()]
    def export_catalog(self,output_path=None):
        path=output_path or os.path.join(self.output_dir,"catalog.json")
        data=[{"filename":ss.filename,"category":ss.category,"text":ss.text_content[:100],"size":str(ss.width)+"x"+str(ss.height),"timestamp":ss.timestamp} for ss in self.screenshots]
        with open(path,"w") as f:json.dump(data,f,indent=2)
        print("Catalog: "+path)

def main():
    parser=argparse.ArgumentParser(description="Auto Screenshot Organizer")
    parser.add_argument("--source"); parser.add_argument("--output")
    subparsers=parser.add_subparsers(dest="command")
    subparsers.add_parser("scan"); subparsers.add_parser("organize")
    org_p=subparsers.add_parser("organize-move")
    subparsers.add_parser("duplicates")
    search_p=subparsers.add_parser("search"); search_p.add_argument("query")
    subparsers.add_parser("catalog")
    args=parser.parse_args()
    org=ScreenshotOrganizer(source_dir=args.source,output_dir=args.output)
    if args.command=="scan":
        results=org.scan_directory()
        for ss in results:print("  ["+ss.category+"] "+ss.filename)
    elif args.command=="organize":org.scan_directory();org.organize(copy=True)
    elif args.command=="organize-move":org.scan_directory();org.organize(copy=False)
    elif args.command=="duplicates":org.scan_directory();org.find_duplicates()
    elif args.command=="search":
        org.scan_directory()
        for ss in org.search(args.query):print("  "+ss.filename+": "+ss.text_content[:60])
    elif args.command=="catalog":org.scan_directory();org.export_catalog()
    else:parser.print_help()

if __name__=="__main__":
    main()
